@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo Дон под контролем — подготовка входа в MAX.
echo Сейчас идёт подготовка библиотек. Ничего вводить пока не нужно.
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 -m venv .venv
if errorlevel 1 goto failed
goto install
:use_python
python -m venv .venv
if errorlevel 1 goto failed
:install
.venv\Scripts\python.exe -m pip install --disable-pip-version-check --quiet -r requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe renew_max.py
goto end
:failed
echo Подготовка не завершилась. Нужен Python 3.10 или новее и доступ к PyPI.
echo Сделай снимок этого окна и отправь Алисе. Не отправляй файлы сессии.
pause
:end
endlocal
