@echo off
REM setup.bat

echo 🏠 Setup Gestionale Immobiliare

REM Crea virtual environment
python -m venv venv
call venv\Scripts\activate.bat

REM Installa dipendenze
pip install --upgrade pip
pip install -r requirements.txt

REM Inizializza database
python -c "from src.db import db; db._init_database(); db.seed_demo_data(); print('✅ Database inizializzato')"

REM Crea immagini placeholder
if not exist data\images mkdir data\images
python -c "from PIL import Image, ImageDraw; import os; nomi=['appartamento_centro.jpg','villa_lago.jpg','monolocale.jpg']; [Image.new('RGB',(800,600),color=(73,109,137)).save(f'data/images/{n}') for n in nomi]; print('✅ Immagini create')"

echo ✅ Setup completato! Avvia con: run.bat
pause