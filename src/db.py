from supabase import create_client, Client
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY in environment")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class DatabaseManager:
    def __init__(self):
        self.table = supabase.table("proprieta")

    def create_proprieta(self, data: Dict[str, Any]) -> Optional[int]:
        # booleans should be real bools (True/False)
        if "mensilita_pagata" in data and isinstance(data["mensilita_pagata"], int):
            data["mensilita_pagata"] = bool(data["mensilita_pagata"])
        resp = self.table.insert(data).execute()
        return resp.data[0]["id"] if resp.data else None

    def get_all_proprieta(self, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        q = self.table.select("*")
        f = filters or {}

        if f.get("solo_affitti"):
            q = q.not_.is_("affittato_a", None)  # IS NOT NULL
        if f.get("non_pagati"):
            q = q.eq("mensilita_pagata", False).not_.is_("affittato_a", None)

        # Optional ordering (default by name case-insensitive asc)
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

# Global instance (mirrors your old usage)
db = DatabaseManager()
