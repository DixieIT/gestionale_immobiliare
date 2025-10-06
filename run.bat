@echo off
REM run.bat
call venv\Scripts\activate.bat
streamlit run src/main.py --server.port 8501 --server.headless true
pause