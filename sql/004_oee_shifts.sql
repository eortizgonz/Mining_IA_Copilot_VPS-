ALTER TABLE machine_oee_readings
    ADD COLUMN IF NOT EXISTS work_shift_id integer REFERENCES work_shifts(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS ix_machine_oee_shift_time
    ON machine_oee_readings (work_shift_id, recorded_at DESC);
