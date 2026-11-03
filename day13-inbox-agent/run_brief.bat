@echo off
rem Day 14: Windows Task Scheduler runs this file every morning.
rem It makes the morning brief and keeps a log of what happened.
cd /d "%~dp0"
set PYTHONUTF8=1
echo ===== %date% %time% ===== >> scheduled-log.txt
uv run inbox_agent.py >> scheduled-log.txt 2>&1