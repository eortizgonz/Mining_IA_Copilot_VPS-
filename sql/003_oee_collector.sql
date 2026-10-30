CREATE TABLE IF NOT EXISTS machine_oee_readings (
    id bigserial PRIMARY KEY,
    machine_id integer NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    recorded_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    interval_minutes double precision NOT NULL CHECK (interval_minutes > 0),
    planned_minutes double precision NOT NULL CHECK (planned_minutes >= 0),
    downtime_minutes double precision NOT NULL CHECK (downtime_minutes >= 0 AND downtime_minutes <= planned_minutes),
    target_tons double precision NOT NULL CHECK (target_tons >= 0),
    actual_tons double precision NOT NULL CHECK (actual_tons >= 0),
    conforming_tons double precision NOT NULL CHECK (conforming_tons >= 0 AND conforming_tons <= actual_tons),
    availability double precision NOT NULL CHECK (availability BETWEEN 0 AND 100),
    performance double precision NOT NULL CHECK (performance BETWEEN 0 AND 100),
    quality double precision NOT NULL CHECK (quality BETWEEN 0 AND 100),
    oee double precision NOT NULL CHECK (oee BETWEEN 0 AND 100),
    status varchar(20) NOT NULL CHECK (status IN ('excellent','healthy','warning','critical')),
    source varchar(30) NOT NULL DEFAULT 'rule_collector',
    explanation varchar(500) NOT NULL,
    UNIQUE (machine_id, recorded_at)
);

CREATE INDEX IF NOT EXISTS ix_machine_oee_time ON machine_oee_readings (machine_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS ix_machine_oee_status ON machine_oee_readings (status, recorded_at DESC);
