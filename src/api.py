# src/api.py
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date
from .db import db

app = FastAPI(
    title="Gestionale Immobiliare API",
    version="1.0.0",
    description="API REST per sincronizzazione dati immobiliari"
)

# CORS per chiamate da Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models
class ProprietaBase(BaseModel):
    nome: str = Field(..., min_length=1, max_length=100)
    indirizzo: str
    mq_effettivi: float = Field(..., gt=0)
    mq_commerciali: float = Field(..., gt=0)
    valore_mq: float = Field(..., gt=0)
    affittato_a: Optional[str] = None
    affitto_mensile: float = Field(default=0, ge=0)
    contratto_inizio: Optional[date] = None
    contratto_fine: Optional[date] = None
    mensilita_pagata: bool = False
    immagine_path: Optional[str] = None

class ProprietaCreate(ProprietaBase):
    pass

class ProprietaUpdate(ProprietaBase):
    nome: Optional[str] = None
    indirizzo: Optional[str] = None
    mq_effettivi: Optional[float] = None
    mq_commerciali: Optional[float] = None
    valore_mq: Optional[float] = None

class ProprietaResponse(ProprietaBase):
    id: int
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True

# Endpoints
@app.get("/")
def root():
    return {"message": "Gestionale Immobiliare API v1.0", "status": "online"}

@app.get("/proprieta", response_model=List[ProprietaResponse])
def list_proprieta(
    skip: int = 0,
    limit: int = 100,
    affittato: Optional[bool] = None
):
    """Lista tutte le proprietà con filtri opzionali"""
    filters = {}
    if affittato is not None:
        filters['solo_affitti'] = affittato
    
    proprieta = db.get_all_proprieta(filters)
    return proprieta[skip:skip+limit]

@app.get("/proprieta/{proprieta_id}", response_model=ProprietaResponse)
def get_proprieta(proprieta_id: int):
    """Ottieni dettagli proprietà per ID"""
    prop = db.get_proprieta_by_id(proprieta_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Proprietà non trovata")
    return prop

@app.post("/proprieta", response_model=ProprietaResponse, status_code=201)
def create_proprieta(proprieta: ProprietaCreate):
    """Crea nuova proprietà"""
    try:
        prop_id = db.create_proprieta(proprieta.model_dump())
        return db.get_proprieta_by_id(prop_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/proprieta/{proprieta_id}", response_model=ProprietaResponse)
def update_proprieta(proprieta_id: int, proprieta: ProprietaUpdate):
    """Aggiorna proprietà esistente"""
    if not db.get_proprieta_by_id(proprieta_id):
        raise HTTPException(status_code=404, detail="Proprietà non trovata")
    
    # Rimuovi campi None
    update_data = {k: v for k, v in proprieta.model_dump().items() if v is not None}
    
    try:
        db.update_proprieta(proprieta_id, update_data)
        return db.get_proprieta_by_id(proprieta_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/proprieta/{proprieta_id}", status_code=204)
def delete_proprieta(proprieta_id: int):
    """Elimina proprietà"""
    if not db.delete_proprieta(proprieta_id):
        raise HTTPException(status_code=404, detail="Proprietà non trovata")
    return None

@app.get("/stats")
def get_stats():
    """Statistiche generali"""
    proprieta = db.get_all_proprieta()
    affitti = [p for p in proprieta if p['affittato_a']]
    
    return {
        "totale_immobili": len(proprieta),
        "affitti_attivi": len(affitti),
        "entrate_mensili": sum(p['affitto_mensile'] for p in affitti),
        "valore_patrimonio": sum(p['mq_commerciali'] * p['valore_mq'] for p in proprieta)
    }

# Avvio server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)