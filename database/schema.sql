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
