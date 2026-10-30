import unittest
from unittest.mock import patch

from app import app
from rag_service import resolve_mode


class RagChatTest(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session.update(user_id=1, name="Test", username="test")

    def test_resolve_mode(self):
        self.assertEqual(resolve_mode("¿Cuál máquina tiene mayor riesgo?"), "predictive")
        self.assertEqual(resolve_mode("La trituradora no arranca"), "troubleshooting")
        self.assertEqual(resolve_mode("¿Qué indica el manual de la banda?"), "manuals")
        self.assertEqual(resolve_mode("¿Cuál máquina tiene el menor OEE?"), "oee")

    @patch("app.answer_chat", return_value=("Respuesta", ["Fuente"], "predictive"))
    def test_chat_returns_resolved_mode_and_sources(self, answer_chat):
        response = self.client.post("/api/copilot/chat", json={"question": "¿Cuál equipo tiene mayor riesgo?", "mode": "auto"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"answer": "Respuesta", "sources": ["Fuente"], "mode": "predictive"})
        answer_chat.assert_called_once_with("¿Cuál equipo tiene mayor riesgo?", "auto")

    def test_chat_rejects_invalid_mode(self):
        response = self.client.post("/api/copilot/chat", json={"question": "Consulta válida", "mode": "otro"})
        self.assertEqual(response.status_code, 400)

    @patch("app.oee_dashboard", return_value={"summary": {"oee": 80.0}, "machines": []})
    def test_oee_endpoint(self, dashboard):
        response = self.client.get("/api/oee?days=30")
        self.assertEqual(response.status_code, 200)
        dashboard.assert_called_once_with(30, None)

    @patch("app.turn_dashboard", return_value={"active": True, "shift": {"name": "Turno A"}})
    def test_turn_endpoint(self, dashboard):
        response = self.client.get("/api/turn")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["active"])
        dashboard.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
