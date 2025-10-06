# src/db.py
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from contextlib import contextmanager
try:
    from . import settings
except ImportError:
    import settings

class DatabaseManager:
    def __init__(self, db_path: Path = settings.DB_PATH):
        self.db_path = db_path
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager per connessioni sicure"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Permette accesso per nome colonna
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_database(self):
        """Initialize database only if it doesn't exist yet"""
        with self.get_connection() as conn:
            # check if the table already exists
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='proprieta';"
            ).fetchone()
            if row:
                # table already exists, skip schema execution
                return

            schema_path = settings.BASE_DIR / "schema.sql"
            if schema_path.exists():
                print(f"🗄️  Creating schema from {schema_path}")
                conn.executescript(schema_path.read_text(encoding="utf-8"))
            else:
                # fallback inline schema
                print("🗄️  Creating inline default schema")
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS proprieta (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nome TEXT NOT NULL UNIQUE,
                        indirizzo TEXT NOT NULL,
                        mq_effettivi REAL NOT NULL CHECK(mq_effettivi > 0),
                        mq_commerciali REAL NOT NULL CHECK(mq_commerciali >= mq_effettivi),
                        valore_mq REAL NOT NULL CHECK(valore_mq > 0),
                        affittato_a TEXT,
                        affitto_mensile REAL DEFAULT 0 CHECK(affitto_mensile >= 0),
                        contratto_inizio DATE,
                        contratto_fine DATE,
                        mensilita_pagata BOOLEAN DEFAULT 0,
                        immagine_path TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CHECK(contratto_fine IS NULL OR contratto_fine >= contratto_inizio)
                    );
                """)

    
    def create_proprieta(self, data: Dict[str, Any]) -> int:
        """Crea nuova proprietà"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO proprieta 
                (nome, indirizzo, mq_effettivi, mq_commerciali, valore_mq, 
                 affittato_a, affitto_mensile, contratto_inizio, contratto_fine, 
                 mensilita_pagata, immagine_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['nome'], data['indirizzo'], data['mq_effettivi'],
                data['mq_commerciali'], data['valore_mq'],
                data.get('affittato_a'), data.get('affitto_mensile', 0),
                data.get('contratto_inizio'), data.get('contratto_fine'),
                data.get('mensilita_pagata', 0), data.get('immagine_path')
            ))
            return cursor.lastrowid
    
    def get_all_proprieta(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Recupera tutte le proprietà con filtri opzionali"""
        query = "SELECT * FROM proprieta WHERE 1=1"
        params: list = []

        f = filters or {}  # ✅ evita NoneType

        if f.get('solo_affitti'):
            query += " AND affittato_a IS NOT NULL"
        if f.get('non_pagati'):
            query += " AND mensilita_pagata = 0 AND affittato_a IS NOT NULL"
        if f.get('scadenza_giorni'):
            query += (" AND contratto_fine IS NOT NULL "
                    "AND julianday(contratto_fine) - julianday('now') <= ?")
            params.append(f['scadenza_giorni'])

        # ✅ ORDER BY con whitelist (evita SQL injection e valori sconosciuti)
        allowed_orders = {
            "nome": "nome COLLATE NOCASE ASC",
            "valore_mq DESC": "valore_mq DESC",
            # NULL alla fine, poi ASC per le date presenti
            "contratto_fine ASC": "CASE WHEN contratto_fine IS NULL THEN 1 ELSE 0 END, contratto_fine ASC",
        }
        order_key = f.get('order_by', 'nome')
        order_by = allowed_orders.get(order_key, allowed_orders["nome"])

        query += f" ORDER BY {order_by}"

        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    
    def get_proprieta_by_id(self, prop_id: int) -> Optional[Dict]:
        """Recupera proprietà per ID"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM proprieta WHERE id = ?", (prop_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_proprieta(self, prop_id: int, data: Dict[str, Any]) -> bool:
        """Aggiorna proprietà esistente"""
        fields = []
        values = []
        
        for key, value in data.items():
            if key != 'id':
                fields.append(f"{key} = ?")
                values.append(value)
        
        values.append(prop_id)
        query = f"UPDATE proprieta SET {', '.join(fields)} WHERE id = ?"
        
        with self.get_connection() as conn:
            cursor = conn.execute(query, values)
            return cursor.rowcount > 0
    
    def delete_proprieta(self, prop_id: int) -> bool:
        """Elimina proprietà"""
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM proprieta WHERE id = ?", (prop_id,))
            return cursor.rowcount > 0
    
    def seed_demo_data(self):
        """Popola DB con dati di esempio"""
        demo_data = [
            {
                'nome': 'Appartamento Centro',
                'indirizzo': 'Via Roma 15, Milano',
                'mq_effettivi': 85.0,
                'mq_commerciali': 95.0,
                'valore_mq': 3500.0,
                'affittato_a': 'Mario Rossi',
                'affitto_mensile': 1200.0,
                'contratto_inizio': '2023-01-01',
                'contratto_fine': '2025-12-31',
                'mensilita_pagata': 1,
                'immagine_path': 'appartamento_centro.jpg'
            },
            {
                'nome': 'Villa Lago Como',
                'indirizzo': 'Via Lungolago 8, Como',
                'mq_effettivi': 250.0,
                'mq_commerciali': 280.0,
                'valore_mq': 5000.0,
                'affittato_a': 'Laura Bianchi',
                'affitto_mensile': 2500.0,
                'contratto_inizio': '2024-06-01',
                'contratto_fine': (datetime.now().date().replace(day=1) + 
                                   __import__('datetime').timedelta(days=40)).isoformat(),
                'mensilita_pagata': 0,
                'immagine_path': 'villa_lago.jpg'
            },
            {
                'nome': 'Monolocale Universitario',
                'indirizzo': 'Via Festa del Perdono 3, Milano',
                'mq_effettivi': 35.0,
                'mq_commerciali': 40.0,
                'valore_mq': 2800.0,
                'affittato_a': None,
                'affitto_mensile': 0.0,
                'contratto_inizio': None,
                'contratto_fine': None,
                'mensilita_pagata': 0,
                'immagine_path': 'monolocale.jpg'
            }
        ]
        
        for data in demo_data:
            try:
                self.create_proprieta(data)
            except sqlite3.IntegrityError:
                pass  # Skip se già esiste

# Istanza globale
db = DatabaseManager()