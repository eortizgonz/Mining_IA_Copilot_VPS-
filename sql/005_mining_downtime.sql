CREATE TABLE IF NOT EXISTS mining_downtime_events (
    id bigserial PRIMARY KEY,
    machine_id integer NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    work_shift_id integer REFERENCES work_shifts(id) ON DELETE RESTRICT,
    started_at timestamptz NOT NULL,
    ended_at timestamptz,
    duration_minutes double precision NOT NULL DEFAULT 0 CHECK (duration_minutes >= 0),
    category varchar(60) NOT NULL,
    cause varchar(180) NOT NULL,
    planned boolean NOT NULL DEFAULT false,
    status varchar(20) NOT NULL CHECK (status IN ('open','closed')),
    source varchar(30) NOT NULL DEFAULT 'manual',
    notes varchar(500),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((status='open' AND ended_at IS NULL) OR (status='closed' AND ended_at IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS ix_mining_downtime_machine_time ON mining_downtime_events(machine_id,started_at DESC);
CREATE INDEX IF NOT EXISTS ix_mining_downtime_status ON mining_downtime_events(status,started_at DESC);
CREATE INDEX IF NOT EXISTS ix_mining_downtime_shift ON mining_downtime_events(work_shift_id,started_at DESC);

INSERT INTO mining_downtime_events
    (machine_id,work_shift_id,started_at,ended_at,duration_minutes,category,cause,planned,status,source,notes)
SELECT o.machine_id,o.work_shift_id,o.recorded_at-(o.downtime_minutes * interval '1 minute'),o.recorded_at,
       o.downtime_minutes,'Microparada','Parada histórica derivada del colector OEE.',false,'closed','oee_backfill',
       'Registro inicial recuperado desde machine_oee_readings; validar contra la señal real del equipo.'
FROM machine_oee_readings o
WHERE o.downtime_minutes > 0
  AND NOT EXISTS (
      SELECT 1 FROM mining_downtime_events d
      WHERE d.machine_id=o.machine_id AND d.ended_at=o.recorded_at AND d.source='oee_backfill'
  );
