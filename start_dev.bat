@echo off
REM Sobe os dois serviços do projeto, cada um na sua janela:
REM   - Django (runserver), no venv principal (.venv)
REM   - Classificador de IA (uvicorn), no venv separado (.venv-ia)
REM
REM Feche as janelas (ou Ctrl+C dentro delas) pra parar cada serviço.
REM Sem o classificador rodando, o sistema funciona normalmente — só sem
REM o palpite da IA na dupla checagem.

cd /d %~dp0

start "Django (porta 8000)" cmd /k "call .venv\Scripts\activate.bat && python manage.py runserver 8000"
start "Classificador de IA (porta 8001)" cmd /k "call .venv-ia\Scripts\activate.bat && uvicorn classificador.servico:app --host 0.0.0.0 --port 8001"

echo.
echo Duas janelas foram abertas: Django (8000) e Classificador de IA (8001).
echo A primeira classificacao depois de abrir o servico de IA demora mais
echo (carrega o modelo na memoria) — as seguintes sao rapidas.
echo.
