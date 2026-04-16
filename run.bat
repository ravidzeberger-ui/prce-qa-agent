@echo off
cd /d "%~dp0"
echo.
echo  Installing dependencies...
pip install -r requirements.txt -q
playwright install chromium firefox webkit
echo.
echo  Running PRCE QA Agent...
python qa_agent.py
pause
