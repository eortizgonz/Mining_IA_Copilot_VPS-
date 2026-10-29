CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS machines (
    id serial PRIMARY KEY, code varchar(40) UNIQUE NOT NULL, name varchar(140) NOT NULL,
    machine_type varchar(100) NOT NULL, area varchar(100) NOT NULL,
    max_usage_hours double precision NOT NULL CHECK (max_usage_hours > 0),
    max_vibration double precision NOT NULL CHECK (max_vibration > 0),
    max_temperature double precision NOT NULL,
    rated_current double precision NOT NULL CHECK (rated_current > 0),
    nominal_rpm double precision NOT NULL CHECK (nominal_rpm >= 0),
    max_pressure double precision NOT NULL CHECK (max_pressure >= 0),
    active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id serial PRIMARY KEY, code varchar(40) UNIQUE NOT NULL, name varchar(140) NOT NULL,
    product_type varchar(80) NOT NULL, presentation varchar(120) NOT NULL,
    unit_of_measure varchar(20) NOT NULL DEFAULT 'ton', standard_batch_size integer NOT NULL CHECK (standard_batch_size > 0),
    shelf_life_days integer CHECK (shelf_life_days IS NULL OR shelf_life_days > 0),
    active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sop_chunks (
    id bigserial PRIMARY KEY, document_hash varchar(64) NOT NULL, document_name varchar(255) NOT NULL,
    page integer NOT NULL CHECK (page >= 1), chunk_index integer NOT NULL CHECK (chunk_index >= 0),
    content text NOT NULL, embedding vector NOT NULL, created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (document_hash, page, chunk_index)
);

CREATE TABLE IF NOT EXISTS users (
    id serial PRIMARY KEY, name varchar(120) NOT NULL, email varchar(255) UNIQUE NOT NULL,
    username varchar(80) UNIQUE NOT NULL, password_hash varchar(255) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS work_shifts (
    id serial PRIMARY KEY, code varchar(20) UNIQUE NOT NULL, name varchar(60) NOT NULL,
    start_time time NOT NULL, end_time time NOT NULL, planned_minutes integer NOT NULL CHECK (planned_minutes > 0),
    active boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS machine_readings (
    id bigserial PRIMARY KEY, machine_id integer NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    recorded_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP, usage_hours double precision NOT NULL CHECK (usage_hours >= 0),
    vibration double precision NOT NULL CHECK (vibration >= 0), temperature double precision NOT NULL,
    current_amps double precision NOT NULL CHECK (current_amps >= 0), rpm double precision NOT NULL CHECK (rpm >= 0),
    pressure double precision NOT NULL CHECK (pressure >= 0), failure_probability double precision NOT NULL CHECK (failure_probability BETWEEN 0 AND 100),
    health_status varchar(20) NOT NULL CHECK (health_status IN ('healthy','warning','critical')),
    explanation varchar(500) NOT NULL, UNIQUE (machine_id, recorded_at)
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id bigserial PRIMARY KEY, user_id integer NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash varchar(64) UNIQUE NOT NULL, expires_at timestamptz NOT NULL, used_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS product_routings (
    id serial PRIMARY KEY, product_id integer NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    sequence integer NOT NULL CHECK (sequence > 0), operation_code varchar(40) NOT NULL,
    operation_name varchar(120) NOT NULL, machine_id integer NOT NULL REFERENCES machines(id),
    ideal_cycle_time_seconds double precision NOT NULL CHECK (ideal_cycle_time_seconds > 0),
    setup_minutes integer NOT NULL CHECK (setup_minutes >= 0), UNIQUE (product_id, sequence)
);

CREATE TABLE IF NOT EXISTS production_orders (
    id serial PRIMARY KEY, order_number varchar(40) UNIQUE NOT NULL,
    product_id integer NOT NULL REFERENCES products(id), planned_quantity integer NOT NULL CHECK (planned_quantity > 0),
    planned_start timestamptz NOT NULL, planned_end timestamptz NOT NULL CHECK (planned_end > planned_start),
    status varchar(30) NOT NULL CHECK (status IN ('planned','released','in_progress','completed','cancelled')),
    priority varchar(20) NOT NULL CHECK (priority IN ('low','normal','high','critical')),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS production_batches (
    id serial PRIMARY KEY, batch_number varchar(50) UNIQUE NOT NULL,
    production_order_id integer NOT NULL REFERENCES production_orders(id) ON DELETE CASCADE,
    planned_quantity integer NOT NULL CHECK (planned_quantity > 0), actual_quantity integer NOT NULL DEFAULT 0 CHECK (actual_quantity >= 0),
    started_at timestamptz, completed_at timestamptz, status varchar(30) NOT NULL CHECK (status IN ('planned','in_progress','quality_hold','released','completed','rejected')),
    expiry_date date
);

CREATE TABLE IF NOT EXISTS production_runs (
    id serial PRIMARY KEY, production_order_id integer NOT NULL REFERENCES production_orders(id),
    batch_id integer NOT NULL REFERENCES production_batches(id), product_id integer NOT NULL REFERENCES products(id),
    machine_id integer NOT NULL REFERENCES machines(id), shift_id integer NOT NULL REFERENCES work_shifts(id),
    operation_sequence integer NOT NULL CHECK (operation_sequence > 0), started_at timestamptz NOT NULL, ended_at timestamptz,
    planned_minutes integer NOT NULL CHECK (planned_minutes > 0), ideal_cycle_time_seconds double precision NOT NULL CHECK (ideal_cycle_time_seconds > 0),
    status varchar(30) NOT NULL CHECK (status IN ('planned','running','paused','completed','cancelled'))
);

CREATE TABLE IF NOT EXISTS machine_downtime_events (
    id bigserial PRIMARY KEY, production_run_id integer NOT NULL REFERENCES production_runs(id) ON DELETE CASCADE,
    machine_id integer NOT NULL REFERENCES machines(id), started_at timestamptz NOT NULL, ended_at timestamptz,
    duration_minutes double precision NOT NULL CHECK (duration_minutes >= 0), reason_code varchar(40) NOT NULL,
    reason_description varchar(180) NOT NULL, category varchar(60) NOT NULL, is_planned boolean NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS oee_results (
    id bigserial PRIMARY KEY, production_run_id integer UNIQUE NOT NULL REFERENCES production_runs(id) ON DELETE CASCADE,
    calculated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    availability double precision NOT NULL CHECK (availability BETWEEN 0 AND 100),
    performance double precision NOT NULL CHECK (performance BETWEEN 0 AND 100),
    quality double precision NOT NULL CHECK (quality BETWEEN 0 AND 100), oee double precision NOT NULL CHECK (oee BETWEEN 0 AND 100),
    operating_minutes double precision NOT NULL CHECK (operating_minutes >= 0), downtime_minutes double precision NOT NULL CHECK (downtime_minutes >= 0),
    total_units integer NOT NULL CHECK (total_units >= 0), good_units integer NOT NULL CHECK (good_units >= 0)
);

CREATE TABLE IF NOT EXISTS production_counters (
    id bigserial PRIMARY KEY, production_run_id integer NOT NULL REFERENCES production_runs(id) ON DELETE CASCADE,
    recorded_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP, total_units integer NOT NULL CHECK (total_units >= 0),
    good_units integer NOT NULL CHECK (good_units >= 0), rejected_units integer NOT NULL CHECK (rejected_units >= 0),
    rework_units integer NOT NULL CHECK (rework_units >= 0), CHECK (good_units + rejected_units <= total_units)
);

CREATE INDEX IF NOT EXISTS ix_sop_chunks_document_hash ON sop_chunks (document_hash);
CREATE INDEX IF NOT EXISTS users_email_lower_idx ON users (lower(email));
CREATE INDEX IF NOT EXISTS users_username_lower_idx ON users (lower(username));
CREATE INDEX IF NOT EXISTS ix_machine_readings_health_status ON machine_readings (health_status);
CREATE INDEX IF NOT EXISTS ix_machine_readings_machine_time ON machine_readings (machine_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS password_reset_tokens_expiry_idx ON password_reset_tokens (expires_at) WHERE used_at IS NULL;
CREATE INDEX IF NOT EXISTS password_reset_tokens_user_idx ON password_reset_tokens (user_id);
CREATE INDEX IF NOT EXISTS ix_product_routings_machine_id ON product_routings (machine_id);
CREATE INDEX IF NOT EXISTS ix_production_orders_status ON production_orders (status);
CREATE INDEX IF NOT EXISTS ix_production_batches_order ON production_batches (production_order_id);
CREATE INDEX IF NOT EXISTS ix_production_batches_status ON production_batches (status);
CREATE INDEX IF NOT EXISTS ix_production_runs_machine_time ON production_runs (machine_id, started_at DESC);
CREATE INDEX IF NOT EXISTS ix_production_runs_order ON production_runs (production_order_id);
CREATE INDEX IF NOT EXISTS ix_downtime_machine_time ON machine_downtime_events (machine_id, started_at DESC);
CREATE INDEX IF NOT EXISTS ix_downtime_reason ON machine_downtime_events (reason_code);
CREATE INDEX IF NOT EXISTS ix_production_counters_run_time ON production_counters (production_run_id, recorded_at DESC);
