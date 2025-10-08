from supabase import create_client, Client
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
import os, re, uuid, pathlib

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
# Per upload lato server, meglio la SERVICE_ROLE_KEY (ha permessi su Storage con RLS attive)
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY in environment")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configura questi nomi per il tuo progetto
BUCKET_NAME = "piantine" 
IMG_URL_COL = "immagine_url"
IMG_PATH_COL = "immagine_path"

def _safe_filename(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9._-]+", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return name or str(uuid.uuid4())

class DatabaseManager:
    def __init__(self):
        self.table = supabase.table("proprieta")

    # --- CRUD esistenti -------------------------------------------------------
    def create_proprieta(self, data: Dict[str, Any]) -> Optional[int]:
        if "mensilita_pagata" in data and isinstance(data["mensilita_pagata"], int):
            data["mensilita_pagata"] = bool(data["mensilita_pagata"])
        resp = self.table.insert(data).execute()
        return resp.data[0]["id"] if resp.data else None

    def get_all_proprieta(self, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        q = self.table.select("*")
        f = filters or {}

        if f.get("solo_affitti"):
            q = q.not_.is_("affittato_a", None)
        if f.get("non_pagati"):
            q = q.eq("mensilita_pagata", False).not_.is_("affittato_a", None)

        order_key = (f.get("order_by") or "nome").split()[0]
        order_desc = "DESC" in (f.get("order_by") or "")
        q = q.order(order_key, desc=order_desc)

        resp = q.execute()
        return resp.data or []

    def get_proprieta_by_id(self, prop_id: int) -> Optional[Dict[str, Any]]:
        resp = self.table.select("*").eq("id", prop_id).limit(1).execute()
        return resp.data[0] if resp.data else None

    def update_proprieta(self, prop_id: int, data: Dict[str, Any]) -> bool:
        if "mensilita_pagata" in data and isinstance(data["mensilita_pagata"], int):
            data["mensilita_pagata"] = bool(data["mensilita_pagata"])
        resp = self.table.update(data).eq("id", prop_id).execute()
        return bool(resp.data)

    def delete_proprieta(self, prop_id: int) -> bool:
        resp = self.table.delete().eq("id", prop_id).execute()
        return bool(resp.data)


    def upload_piantina_and_link(
        self,
        prop_id: int,
        local_file_path: str,
        *,
        filename: Optional[str] = None,
        make_public_url: bool = True,
        upsert: bool = True,
    ) -> Dict[str, Any]:
        """
        Carica una piantina nel bucket e aggiorna il record della proprieta' con:
          - URL pubblico (se make_public_url=True)
          - path nel bucket (sempre, nella colonna IMG_PATH_COL se esiste)
        Ritorna dizionario con {path, public_url (se richiesto)}.
        """
        # 1) prepara path remoto: <prop_id>/<filename-sicuro>
        filename = filename or pathlib.Path(local_file_path).name
        safe_name = _safe_filename(filename)
        remote_path = f"{prop_id}/{safe_name}"

        # 2) upload nel bucket
        with open(local_file_path, "rb") as f:
            # upsert=True evita errore se ricarichi con lo stesso nome
            supabase.storage.from_(BUCKET_NAME).upload(remote_path, f)

        # 3) ottieni URL (pubblico o firmato)
        public_url = None
        if make_public_url:
            res = supabase.storage.from_(BUCKET_NAME).get_public_url(remote_path)
            public_url = res.get("data", {}).get("publicUrl")

        # 4) aggiorna record tabella
        update_payload: Dict[str, Any] = {}
        if IMG_URL_COL:
            update_payload[IMG_URL_COL] = public_url or None
        if IMG_PATH_COL:
            update_payload[IMG_PATH_COL] = remote_path

        if update_payload:
            self.update_proprieta(prop_id, update_payload)

        return {"path": remote_path, "public_url": public_url}

    def get_signed_piantina_url(self, prop_id: int, expires_seconds: int = 3600) -> Optional[str]:
        """
        Se il bucket e' privato, usa il PATH salvato per generare una Signed URL temporanea.
        """
        rec = self.get_proprieta_by_id(prop_id)
        if not rec:
            return None

        path = rec.get(IMG_PATH_COL) or ""
        if not path:
            return None

        data = supabase.storage.from_(BUCKET_NAME).create_signed_url(path, expires_seconds)
        return data.get("signedUrl")

    def remove_piantina(self, prop_id: int) -> bool:
        """
        Cancella la piantina dal bucket (usando il PATH salvato) e azzera i campi nel DB.
        """
        rec = self.get_proprieta_by_id(prop_id)
        if not rec:
            return False

        path = rec.get(IMG_PATH_COL)
        if path:
            supabase.storage.from_(BUCKET_NAME).remove([path])

        payload = {}
        if IMG_URL_COL:
            payload[IMG_URL_COL] = None
        if IMG_PATH_COL:
            payload[IMG_PATH_COL] = None
        return self.update_proprieta(prop_id, payload)

# istanza globale
db = DatabaseManager()
