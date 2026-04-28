CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE site (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    site_type VARCHAR(30) NOT NULL,
    location VARCHAR(200) NOT NULL,
    country VARCHAR(100) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE app_user (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES site(id),
    origin_site_code VARCHAR(20) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(200) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(50) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE client (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    origin_site_code VARCHAR(20) NOT NULL,
    company_name VARCHAR(200) NOT NULL,
    contact_name VARCHAR(150) NOT NULL,
    contact_email VARCHAR(200) UNIQUE NOT NULL,
    contact_phone VARCHAR(30),
    country VARCHAR(100) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE vehicle (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES site(id),
    origin_site_code VARCHAR(20) NOT NULL,
    registration_no VARCHAR(30) UNIQUE NOT NULL,
    vehicle_type VARCHAR(50) NOT NULL,
    capacity_teu INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE driver (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES app_user(id),
    origin_site_code VARCHAR(20) NOT NULL,
    licence_no VARCHAR(50) UNIQUE NOT NULL,
    licence_expiry DATE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE consignment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES client(id),
    origin_site_id UUID NOT NULL REFERENCES site(id),
    destination_site_id UUID NOT NULL REFERENCES site(id),
    origin_site_code VARCHAR(20) NOT NULL,
    reference_no VARCHAR(50) UNIQUE NOT NULL,
    notes TEXT,
    created_by_id UUID NOT NULL REFERENCES app_user(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE container (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consignment_id UUID NOT NULL REFERENCES consignment(id),
    origin_site_code VARCHAR(20) NOT NULL,
    container_no VARCHAR(20) UNIQUE NOT NULL,
    container_type VARCHAR(30) NOT NULL,
    seal_no VARCHAR(50),
    gross_weight_kg NUMERIC(10,2),
    cargo_description TEXT,
    created_by_id UUID NOT NULL REFERENCES app_user(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE trip (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    origin_site_id UUID NOT NULL REFERENCES site(id),
    destination_site_id UUID NOT NULL REFERENCES site(id),
    vehicle_id UUID NOT NULL REFERENCES vehicle(id),
    driver_id UUID NOT NULL REFERENCES driver(id),
    origin_site_code VARCHAR(20) NOT NULL,
    status VARCHAR(30) NOT NULL,
    planned_departure TIMESTAMPTZ NOT NULL,
    actual_departure TIMESTAMPTZ,
    actual_arrival TIMESTAMPTZ,
    created_by_id UUID NOT NULL REFERENCES app_user(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE trip_container (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trip_id UUID NOT NULL REFERENCES trip(id),
    container_id UUID NOT NULL REFERENCES container(id),
    origin_site_code VARCHAR(20) NOT NULL,
    loaded_at TIMESTAMPTZ,
    unloaded_at TIMESTAMPTZ,
    assigned_by_id UUID NOT NULL REFERENCES app_user(id),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    active_assignment BOOLEAN,
    CONSTRAINT uq_trip_container_pair UNIQUE (trip_id, container_id)
);

CREATE TABLE handover (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trip_id UUID NOT NULL REFERENCES trip(id),
    container_id UUID NOT NULL REFERENCES container(id),
    from_site_id UUID NOT NULL REFERENCES site(id),
    to_site_id UUID NOT NULL REFERENCES site(id),
    sender_user_id UUID NOT NULL REFERENCES app_user(id),
    receiver_user_id UUID NOT NULL REFERENCES app_user(id),
    origin_site_code VARCHAR(20) NOT NULL,
    seal_verified BOOLEAN NOT NULL,
    seal_no VARCHAR(50),
    handover_time TIMESTAMPTZ NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_handover_distinct_sites CHECK (from_site_id <> to_site_id)
);

CREATE TABLE milestone (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trip_id UUID NOT NULL REFERENCES trip(id),
    container_id UUID NOT NULL REFERENCES container(id),
    site_id UUID NOT NULL REFERENCES site(id),
    recorded_by_id UUID NOT NULL REFERENCES app_user(id),
    origin_site_code VARCHAR(20) NOT NULL,
    milestone_type VARCHAR(50) NOT NULL,
    milestone_time TIMESTAMPTZ NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE incident (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trip_id UUID NOT NULL REFERENCES trip(id),
    container_id UUID REFERENCES container(id),
    site_id UUID NOT NULL REFERENCES site(id),
    reported_by_id UUID NOT NULL REFERENCES app_user(id),
    resolved_by_id UUID REFERENCES app_user(id),
    origin_site_code VARCHAR(20) NOT NULL,
    incident_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    incident_time TIMESTAMPTZ NOT NULL,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE event_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    origin_site_code VARCHAR(20) NOT NULL,
    entity_name VARCHAR(50) NOT NULL,
    record_id UUID NOT NULL,
    operation VARCHAR(10) NOT NULL,
    payload JSONB NOT NULL,
    performed_by_id UUID NOT NULL REFERENCES app_user(id),
    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE replication_issue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_code VARCHAR(20) NOT NULL,
    subscription_name VARCHAR(100) NOT NULL,
    issue_type VARCHAR(50) NOT NULL,
    detail TEXT NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_resolved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE bootstrap_state (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE container_state_projection (
    container_id UUID PRIMARY KEY,
    consignment_id UUID NOT NULL,
    container_no VARCHAR(20) NOT NULL,
    consignment_ref VARCHAR(50) NOT NULL,
    current_status VARCHAR(50) NOT NULL,
    current_site_name VARCHAR(100),
    current_site_code VARCHAR(20),
    latest_milestone_type VARCHAR(50),
    latest_milestone_time TIMESTAMPTZ,
    last_handover_time TIMESTAMPTZ,
    trip_id UUID,
    trip_status VARCHAR(30),
    refreshed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_origin_site_code_user ON app_user(origin_site_code);
CREATE INDEX idx_origin_site_code_client ON client(origin_site_code);
CREATE INDEX idx_origin_site_code_vehicle ON vehicle(origin_site_code);
CREATE INDEX idx_origin_site_code_driver ON driver(origin_site_code);
CREATE INDEX idx_origin_site_code_consignment ON consignment(origin_site_code);
CREATE INDEX idx_origin_site_code_container ON container(origin_site_code);
CREATE INDEX idx_origin_site_code_trip ON trip(origin_site_code);
CREATE UNIQUE INDEX ux_trip_vehicle_active
    ON trip(vehicle_id)
    WHERE status IN ('PLANNED', 'DEPARTED', 'IN_TRANSIT', 'ARRIVED');
CREATE UNIQUE INDEX ux_trip_driver_active
    ON trip(driver_id)
    WHERE status IN ('PLANNED', 'DEPARTED', 'IN_TRANSIT', 'ARRIVED');
CREATE INDEX idx_origin_site_code_trip_container ON trip_container(origin_site_code);
CREATE UNIQUE INDEX ux_trip_container_active
    ON trip_container(container_id)
    WHERE active_assignment IS TRUE;
CREATE INDEX idx_origin_site_code_handover ON handover(origin_site_code);
CREATE INDEX idx_origin_site_code_milestone ON milestone(origin_site_code);
CREATE INDEX idx_origin_site_code_incident ON incident(origin_site_code);
CREATE INDEX idx_event_log_origin_site ON event_log(origin_site_code);
