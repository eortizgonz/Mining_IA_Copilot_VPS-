import hashlib
import json
import os
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path

from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader
from pptx import Presentation
import xlrd

from database import connect


ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".pptx", ".txt", ".md", ".csv", ".json", ".html", ".htm", ".xml"}


def _ollama(path, payload):
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    request = urllib.request.Request(f"{base_url}{path}", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=int(os.getenv("OLLAMA_TIMEOUT", "300"))) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"No fue posible conectar con Ollama en {base_url}: {exc}") from exc


def _embed(texts):
    return _ollama("/api/embed", {"model": os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"), "input": texts})["embeddings"]


def _chunks(text, size=1200, overlap=200):
    clean = " ".join(text.split())
    return [clean[start:start + size] for start in range(0, len(clean), size - overlap) if clean[start:start + size].strip()]


def _vector(values):
    return "[" + ",".join(f"{float(value):.9g}" for value in values) + "]"


def ingest_pages(document_name, pages, raw=None):
    records = [(page, index, chunk) for page, text in pages for index, chunk in enumerate(_chunks(text))]
    if not records:
        raise ValueError("El documento no contiene texto indexable.")
    source = raw if raw is not None else "\n".join(text for _, text in pages).encode()
    digest = hashlib.sha256(source).hexdigest()
    embeddings = _embed([record[2] for record in records])
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("DELETE FROM sop_chunks WHERE document_name=%s", (document_name,))
        for (page, index, content), embedding in zip(records, embeddings):
            cursor.execute("""INSERT INTO sop_chunks
                (document_hash,document_name,page,chunk_index,content,embedding)
                VALUES (%s,%s,%s,%s,%s,%s::vector)""",
                (digest, document_name, page, index, content, _vector(embedding)))
        connection.commit()
    return len(records)


def ingest_text(document_name, text):
    return ingest_pages(document_name, [(1, text)], text.encode())


def extract_document(filename, raw):
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValueError(f"Tipo de archivo no compatible: {extension or 'sin extensión'}")
    stream = BytesIO(raw)
    if extension == ".pdf":
        return [(index + 1, page.extract_text() or "") for index, page in enumerate(PdfReader(stream).pages)]
    if extension == ".docx":
        return [(1, "\n".join(p.text for p in Document(stream).paragraphs))]
    if extension == ".xlsx":
        workbook = load_workbook(stream, read_only=True, data_only=True)
        return [(i + 1, f"Hoja: {sheet.title}\n" + "\n".join(" | ".join(str(v) for v in row if v is not None) for row in sheet.iter_rows(values_only=True))) for i, sheet in enumerate(workbook.worksheets)]
    if extension == ".xls":
        workbook = xlrd.open_workbook(file_contents=raw)
        return [(i + 1, f"Hoja: {sheet.name}\n" + "\n".join(" | ".join(str(sheet.cell_value(r, c)) for c in range(sheet.ncols)) for r in range(sheet.nrows))) for i, sheet in enumerate(workbook.sheets())]
    if extension == ".pptx":
        presentation = Presentation(stream)
        return [(i + 1, "\n".join(shape.text for shape in slide.shapes if hasattr(shape, "text"))) for i, slide in enumerate(presentation.slides)]
    return [(1, raw.decode("utf-8", errors="replace"))]


def ingest_document(filename, raw):
    return ingest_pages(filename, extract_document(filename, raw), raw)


def list_documents():
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""SELECT document_name,count(*) AS chunks,min(created_at) AS indexed_at
            FROM sop_chunks GROUP BY document_name ORDER BY document_name""")
        return cursor.fetchall()


def delete_document(document_name):
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("DELETE FROM sop_chunks WHERE document_name=%s RETURNING id", (document_name,))
        rows = cursor.fetchall()
        connection.commit()
        return len(rows)


def retrieve(question, limit=4):
    query = _vector(_embed([question])[0])
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""SELECT document_name,page,content,embedding <=> %s::vector AS distance
            FROM sop_chunks ORDER BY embedding <=> %s::vector LIMIT %s""", (query, query, limit))
        return cursor.fetchall()


def answer_rag(question):
    chunks = retrieve(question)
    if not chunks:
        raise ValueError("No hay documentación indexada.")
    evidence, sources = [], []
    for chunk in chunks:
        label = f"{chunk['document_name']} · página {chunk['page']}"
        evidence.append(f"[{label}]\n{chunk['content']}")
        if label not in sources:
            sources.append(label)
    prompt = f"""Responde en español usando exclusivamente la evidencia recuperada. No inventes datos.
Prioriza parada segura, control de energías, LOTO, HSE y las instrucciones del fabricante.
No autorices retirar guardas, anular protecciones ni intervenir equipos energizados.
Si falta evidencia, indícalo. Cita las fuentes entre corchetes. Máximo 220 palabras, texto plano.

EVIDENCIA:
{chr(10).join(evidence)}

PREGUNTA: {question}"""
    result = _ollama("/api/chat", {"model": os.getenv("OLLAMA_CHAT_MODEL", "llama3.1:8b"), "messages": [
        {"role": "system", "content": "Eres un copiloto documental de mantenimiento para extracción y manejo de carbón. No sustituyes al personal autorizado."},
        {"role": "user", "content": prompt}], "stream": False, "options": {"temperature": 0.1, "num_ctx": 4096, "num_predict": 320}})
    return result["message"]["content"], sources
