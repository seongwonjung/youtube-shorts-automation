@echo off
cd /d "%~dp0.."
echo Discord 에이전트 폴러 시작...
echo 중단하려면 Ctrl+C

REM httpx가 없으면 설치
python -c "import httpx" 2>nul || pip install httpx -q

python discord_agent/poller.py
