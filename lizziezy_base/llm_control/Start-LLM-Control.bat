@echo off
setlocal
cd /d "%~dp0"
if exist "..\..\.venv\Scripts\python.exe" (
  "..\..\.venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 18100 --reload
) else (
  python -m uvicorn app:app --host 127.0.0.1 --port 18100 --reload
)
endlocal
