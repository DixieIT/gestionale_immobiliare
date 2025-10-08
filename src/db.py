from supabase import create_client, Client
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
import os, re, uuid, pathlib

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
# Server-side: prefer SERVICE_ROLE_KEY (permessi completi con RLS/Storage)
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY in environment")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Storage config -----------------------------------------------------------
PIANTINE_BUCKET = "piantine"
IMG_URL_COL  = "immagine_url"
IMG_PATH_COL = "immagine_path"

CONTRACT_BUCKET   = "contratti"
CONTRACT_URL_COL  = "contratto_url"
CONTRACT_PATH_COL = "contratto_path"


# --- Helpers -----------------------------------------------------------------
def _safe_filename(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9._-]+", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return name or str(uuid.uuid4())

def _as_public_url(res) -> Optional[str]:
    """Normalize get_public_url(...) return value across supabase-py versions."""
    if isinstance(res, str):
        return res
    if isinstance(res, dict):
        # supabase-py v2 often: {'data': {'publicUrl': '...'}}
        return (
            res.get("publicUrl")
            or (res.get("data") or {}).get("publicUrl")
            or (res.get("data") or {}).get("publicURL")
        )
    return None

def _as_signed_url(res) -> Optional[str]:
    """Normalize create_signed_url(...) return value across supabase-py versions."""
    if isinstance(res, str):
        return res
    if isinstance(res, dict):
        # keys seen in the wild: signedURL / signedUrl, sometimes under data
        return (
            res.get("signedURL")
            or res.get("signedUrl")
            or (res.get("data") or {}).get("signedURL")
            or (res.get("data") or {}).get("signedUrl")
        )
    return None


# --- DB Manager --------------------------------------------------------------
class DatabaseManager:
    def __init__(self):
        self.table = supabase.table("proprieta")

    # CRUD
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
        item = resp.data[0] if resp.data else None
        # Ensure a dict (avoid 'str has no attribute get' in the UI)
        return item if isinstance(item, dict) else None

    def update_proprieta(self, prop_id: int, data: Dict[str, Any]) -> bool:
        if "mensilita_pagata" in data and isinstance(data["mensilita_pagata"], int):
            data["mensilita_pagata"] = bool(data["mensilita_pagata"])
        resp = self.table.update(data).eq("id", prop_id).execute()
        return bool(resp.data)

    def delete_proprieta(self, prop_id: int) -> bool:
        resp = self.table.delete().eq("id", prop_id).execute()
        return bool(resp.data)

    # --- PIANTINE (images) ---------------------------------------------------
    def upload_piantina_and_link(
        self,
        prop_id: int,
        local_file_path: str,
        *,
        filename: Optional[str] = None,
        make_public_url: bool = True,
    ) -> Dict[str, Any]:
        """
        Upload image to 'piantine/<prop_id>/<filename>' and update DB with URL+path.
        """
        filename = filename or pathlib.Path(local_file_path).name
        safe_name = _safe_filename(filename)
        remote_path = f"{prop_id}/{safe_name}"

        # Upload (avoid options with bools)
        with open(local_file_path, "rb") as f:
            supabase.storage.from_(PIANTINE_BUCKET).upload(remote_path, f)

        public_url = None
        if make_public_url:
            res = supabase.storage.from_(PIANTINE_BUCKET).get_public_url(remote_path)
            public_url = _as_public_url(res)

        payload: Dict[str, Any] = {}
        if IMG_URL_COL:
            payload[IMG_URL_COL] = public_url or None
        if IMG_PATH_COL:
            payload[IMG_PATH_COL] = remote_path

        if payload:
            self.update_proprieta(prop_id, payload)

        return {"path": remote_path, "public_url": public_url}

    def get_signed_piantina_url(self, prop_id: int, expires_seconds: int = 3600) -> Optional[str]:
        """
        Return signed URL for a private image if path is stored.
        """
        rec = self.get_proprieta_by_id(prop_id)
        if not rec:
            return None
        path = rec.get(IMG_PATH_COL) or ""
        if not path:
            return None

        res = supabase.storage.from_(PIANTINE_BUCKET).create_signed_url(path, expires_seconds)
        return _as_signed_url(res)

    def remove_piantina(self, prop_id: int) -> bool:
        rec = self.get_proprieta_by_id(prop_id)
        if not rec:
            return False
        path = rec.get(IMG_PATH_COL)
        if path:
            supabase.storage.from_(PIANTINE_BUCKET).remove([path])

        payload = {}
        if IMG_URL_COL:
            payload[IMG_URL_COL] = None
        if IMG_PATH_COL:
            payload[IMG_PATH_COL] = None
        return self.update_proprieta(prop_id, payload)

    # --- CONTRATTI (PDFs) ----------------------------------------------------
    def upload_contratto_and_link(
        self,
        prop_id: int,
        local_file_path: str,
        *,
        filename: Optional[str] = None,
        make_public_url: bool = True,
    ) -> Dict[str, Any]:
        filename = filename or pathlib.Path(local_file_path).name
        safe_name = _safe_filename(filename)
        remote_path = f"{prop_id}/{safe_name}"

        # Upload with correct content type from the start
        with open(local_file_path, "rb") as f:
            supabase.storage.from_(CONTRACT_BUCKET).upload(
                remote_path,
                f,
                file_options={
                    "contentType": "application/pdf",
                    "content-type": "application/pdf",
                }
            )

        # Save a clean public URL (no trailing '?')
        public_url = None
        if make_public_url:
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/{CONTRACT_BUCKET}/{remote_path}"

        self.update_proprieta(
            prop_id,
            {
                CONTRACT_PATH_COL: remote_path,
                CONTRACT_URL_COL: public_url,
            },
        )
        return {"path": remote_path, "public_url": public_url}


    def get_signed_contratto_url(self, prop_id: int, expires_seconds: int = 3600) -> Optional[str]:
        """
        Return signed URL for a private contract if path is stored.
        """
        rec = self.get_proprieta_by_id(prop_id)
        if not rec:
            return None
        path = rec.get(CONTRACT_PATH_COL)
        if not path:
            return None

        res = supabase.storage.from_(CONTRACT_BUCKET).create_signed_url(path, expires_seconds)
        return _as_signed_url(res)


# istanza globale
db = DatabaseManager()
