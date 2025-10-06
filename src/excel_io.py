# src/excel_io.py
import pandas as pd
from pathlib import Path
from typing import List, Dict
try:
    from . import settings
    from .db import db
except ImportError:
    import settings
    from db import db

class ExcelIO:
    COLUMNS_MAPPING = {
        'Nome': 'nome',
        'Indirizzo': 'indirizzo',
        'MQ Effettivi': 'mq_effettivi',
        'MQ Commerciali': 'mq_commerciali',
        'Valore €/m²': 'valore_mq',
        'Affittato A': 'affittato_a',
        'Canone Mensile €': 'affitto_mensile',
        'Contratto Inizio': 'contratto_inizio',
        'Contratto Fine': 'contratto_fine',
        'Mese Pagato': 'mensilita_pagata',
        'Foto': 'immagine_path'
    }
    
    @staticmethod
    def export_to_excel(filepath: Path):
        """Esporta tutte le proprietà in Excel"""
        proprieta = db.get_all_proprieta()
        
        # Converti in DataFrame
        df = pd.DataFrame(proprieta)
        
        # Rinomina colonne per Excel
        reverse_mapping = {v: k for k, v in ExcelIO.COLUMNS_MAPPING.items()}
        df.rename(columns=reverse_mapping, inplace=True)
        
        # Converti booleani
        if 'Mese Pagato' in df.columns:
            df['Mese Pagato'] = df['Mese Pagato'].apply(lambda x: 'SI' if x else 'NO')
        
        # Rimuovi colonne tecniche
        cols_to_remove = ['id', 'created_at', 'updated_at']
        df.drop(columns=[c for c in cols_to_remove if c in df.columns], inplace=True)
        
        # Salva
        df.to_excel(filepath, index=False, engine='openpyxl')
    
    @staticmethod
    def import_from_excel(filepath: Path) -> tuple[int, List[str]]:
        """Importa proprietà da Excel. Returns (count, errors)"""
        df = pd.read_excel(filepath, engine='openpyxl')
        
        # Rinomina colonne
        df.rename(columns=ExcelIO.COLUMNS_MAPPING, inplace=True)
        
        imported_count = 0
        errors = []
        
        for idx, row in df.iterrows():
            try:
                data = row.to_dict()
                
                # Validazioni
                if pd.isna(data.get('nome')):
                    raise ValueError("Nome obbligatorio")
                
                # Converti booleani
                if 'mensilita_pagata' in data:
                    val = str(data['mensilita_pagata']).upper()
                    data['mensilita_pagata'] = 1 if val in ['SI', 'SÌ', '1', 'TRUE'] else 0
                
                # Converti date
                for date_field in ['contratto_inizio', 'contratto_fine']:
                    if date_field in data and pd.notna(data[date_field]):
                        data[date_field] = pd.to_datetime(data[date_field]).strftime('%Y-%m-%d')
                
                # Rimuovi NaN
                data = {k: (v if pd.notna(v) else None) for k, v in data.items()}
                
                db.create_proprieta(data)
                imported_count += 1
                
            except Exception as e:
                errors.append(f"Riga {idx + 2}: {str(e)}")
        
        return imported_count, errors

excel_io = ExcelIO()