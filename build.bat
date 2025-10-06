@echo off
REM build.bat

echo 📦 Building eseguibile...

call venv\Scripts\activate.bat

pyinstaller --onefile ^
    --name="GestionaleImmobiliare" ^
    --add-data "data;data" ^
    --add-data "schema.sql;." ^
    --hidden-import="streamlit" ^
    --hidden-import="pandas" ^
    --hidden-import="openpyxl" ^
    --hidden-import="PIL" ^
    --collect-all streamlit ^
    src/main.py

echo ✅ Eseguibile creato in: dist\GestionaleImmobiliare.exe
echo 📂 Copia la cartella 'data' nella stessa directory dell'eseguibile
pause