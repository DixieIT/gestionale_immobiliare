-- schema.sql
CREATE TABLE IF NOT EXISTS proprieta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    indirizzo TEXT NOT NULL,
    mq_effettivi REAL NOT NULL CHECK(mq_effettivi > 0),
    mq_commerciali REAL NOT NULL CHECK(mq_commerciali >= mq_effettivi),
    valore_mq REAL NOT NULL CHECK(valore_mq > 0),
    affittato_a TEXT,  -- NULL se non affittato
    affitto_mensile REAL DEFAULT 0 CHECK(affitto_mensile >= 0),
    contratto_inizio DATE,  -- ISO 8601: YYYY-MM-DD
    contratto_fine DATE,
    mensilita_pagata BOOLEAN DEFAULT 0,  -- 0=Non pagato, 1=Pagato
    immagine_path TEXT,  -- Path relativo a ./data/images/
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK(contratto_fine IS NULL OR contratto_fine >= contratto_inizio)
);

-- Indici per performance
CREATE INDEX idx_nome ON proprieta(nome);
CREATE INDEX idx_contratto_fine ON proprieta(contratto_fine);
CREATE INDEX idx_mensilita ON proprieta(mensilita_pagata);

