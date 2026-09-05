-- Table unique pour tous les nœuds (scalable 2 → 20+).
-- node_id 0 = paquet LoRa reçu mais illisible (bad_header), source inconnue.

CREATE TABLE IF NOT EXISTS readings (
    id              BIGSERIAL PRIMARY KEY,
    node_id         SMALLINT NOT NULL,
    seq             INTEGER NOT NULL DEFAULT 0,
    temperature     REAL,
    humidity        REAL,
    rssi            SMALLINT,
    snr             REAL,
    uptime_s        BIGINT,
    checksum_ok     BOOLEAN NOT NULL DEFAULT TRUE,
    error           TEXT,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_readings_node_time
    ON readings (node_id, received_at DESC);

CREATE INDEX IF NOT EXISTS idx_readings_received
    ON readings (received_at DESC);

CREATE TABLE IF NOT EXISTS node_stats (
    node_id             SMALLINT PRIMARY KEY,
    last_seq            INTEGER,
    last_seen_at        TIMESTAMPTZ,
    last_rssi           SMALLINT,
    last_snr            REAL,
    last_temperature    REAL,
    last_humidity       REAL,
    packets_received    BIGINT NOT NULL DEFAULT 0,
    packets_missing     BIGINT NOT NULL DEFAULT 0,
    packets_corrupt     BIGINT NOT NULL DEFAULT 0
);

-- Bases déjà créées avant v1.1
ALTER TABLE readings ALTER COLUMN temperature DROP NOT NULL;
ALTER TABLE readings ALTER COLUMN humidity DROP NOT NULL;
ALTER TABLE readings ADD COLUMN IF NOT EXISTS error TEXT;

CREATE TABLE IF NOT EXISTS fl_updates (
    id              BIGSERIAL PRIMARY KEY,
    node_id         SMALLINT NOT NULL,
    seq             INTEGER NOT NULL DEFAULT 0,
    n_samples       INTEGER NOT NULL DEFAULT 0,
    round_id        INTEGER NOT NULL DEFAULT 0,
    w0              REAL,
    w1              REAL,
    w2              REAL,
    w3              REAL,
    rssi            SMALLINT,
    snr             REAL,
    checksum_ok     BOOLEAN NOT NULL DEFAULT TRUE,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fl_updates_node_time
    ON fl_updates (node_id, received_at DESC);

CREATE INDEX IF NOT EXISTS idx_fl_updates_round
    ON fl_updates (round_id, node_id, received_at DESC);

CREATE TABLE IF NOT EXISTS fl_rounds (
    id              SERIAL PRIMARY KEY,
    status          TEXT NOT NULL DEFAULT 'open',
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at       TIMESTAMPTZ,
    timeout_s       INTEGER NOT NULL DEFAULT 90,
    w0              REAL,
    w1              REAL,
    w2              REAL,
    w3              REAL,
    n_total         INTEGER,
    n_nodes         INTEGER
);

CREATE TABLE IF NOT EXISTS fl_commands (
    id              SERIAL PRIMARY KEY,
    cmd             TEXT NOT NULL,
    round_id        INTEGER NOT NULL,
    w0              REAL,
    w1              REAL,
    w2              REAL,
    w3              REAL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acked_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_fl_commands_open
    ON fl_commands (acked_at, created_at);
