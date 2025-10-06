# generate_demo_excel.py
import pandas as pd
from datetime import datetime, timedelta

data = {
    'Nome': ['Appartamento Centro', 'Villa Lago Como', 'Monolocale Universitario'],
    'Indirizzo': [
        'Via Roma 15, Milano',
        'Via Lungolago 8, Como',
        'Via Festa del Perdono 3, Milano'
    ],
    'MQ Effettivi': [85.0, 250.0, 35.0],
    'MQ Commerciali': [95.0, 280.0, 40.0],
    'Valore €/m²': [3500.0, 5000.0, 2800.0],
    'Affittato A': ['Mario Rossi', 'Laura Bianchi', None],
    'Canone Mensile €': [1200.0, 2500.0, 0.0],
    'Contratto Inizio': ['2023-01-01', '2024-06-01', None],
    'Contratto Fine': [
        '2025-12-31',
        (datetime.now() + timedelta(days=45)).strftime('%Y-%m-%d'),
        None
    ],
    'Mese Pagato': ['SI', 'NO', 'NO'],
    'Foto': ['appartamento_centro.jpg', 'villa_lago.jpg', 'monolocale.jpg']
}

df = pd.DataFrame(data)
df.to_excel('proprieta_demo.xlsx', index=False, engine='openpyxl')
print("✅ File proprieta_demo.xlsx creato!")