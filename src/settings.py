# src/settings.py
from pathlib import Path
from typing import Literal

# Percorsi base (configurabile per utente)
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
IMAGES_DIR = DATA_DIR / "images"
DB_PATH = DATA_DIR / "immobiliare.db"

# Crea cartelle se non esistono
DATA_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(exist_ok=True)

# Configurazione sincronizzazione
SYNC_MODE: Literal["local", "api"] = "local"
API_BASE_URL = "http://localhost:8000"  # Modificare per server remoto

# Limiti e validazioni
MAX_IMAGE_SIZE_MB = 5
SUPPORTED_IMAGE_FORMATS = [".jpg", ".jpeg", ".png", ".webp"]
SCADENZA_WARNING_GIORNI = 60