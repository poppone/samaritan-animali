@echo off
REM Genera un video TikTok ZampaViva e lo manda su Telegram.
REM Uso: doppio click, oppure  run_zampaviva.bat handle-del-prodotto
cd /d "%~dp0"
python main.py %*
pause
