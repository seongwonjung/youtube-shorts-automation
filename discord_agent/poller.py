"""
Discord 에이전트 경량 폴러.

Discord API를 직접 폴링해 새 사용자 메시지가 있을 때만
`claude -p`를 호출한다. 메시지가 없으면 Claude를 전혀 사용하지 않으므로
토큰 비용이 거의 0에 가깝다.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

# ── 설정 ──────────────────────────────────────────────
DISCORD_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
CHANNEL_ID = "1494388038782947480"  # #일반 텍스트 채널
BOT_USERNAME = "노트북#0570"
POLL_INTERVAL = 30          # 초 (새 메시지 없을 때 대기)
STATE_FILE = Path(__file__).parent / "state.json"
WORK_DIR = Path(__file__).parent.parent
PROMPT = "discord_agent/prompt.md 파일을 읽고 절차를 따라 실행해줘"

HEADERS = {
    "Authorization": f"Bot {DISCORD_TOKEN}",
    "Content-Type": "application/json",
}
# ──────────────────────────────────────────────────────


def read_last_timestamp() -> str:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))["last_timestamp"]
    except Exception:
        return "0"


def fetch_recent_messages(limit: int = 20) -> list[dict]:
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages?limit={limit}"
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[poller] Discord API error: {e}", flush=True)
        return []


def has_new_user_messages(messages: list[dict], last_ts: str) -> bool:
    """last_timestamp 이후의 봇 외 메시지가 있는지 확인."""
    if last_ts == "0":
        return True
    for msg in messages:
        if msg["timestamp"] > last_ts and not msg["author"].get("bot", False):
            return True
    return False


CLAUDE_CMD = r"C:\Users\jsjsw\AppData\Roaming\npm\claude.cmd"


def run_claude() -> None:
    print("[poller] new message detected -> calling claude -p", flush=True)
    subprocess.run(
        [CLAUDE_CMD, "-p", PROMPT, "--dangerously-skip-permissions"],
        cwd=str(WORK_DIR),
    )
    print("[poller] claude finished", flush=True)


def main() -> None:
    print(f"[poller] started - polling every {POLL_INTERVAL}s", flush=True)
    while True:
        last_ts = read_last_timestamp()
        messages = fetch_recent_messages()
        if messages and has_new_user_messages(messages, last_ts):
            run_claude()
        else:
            print(f"[poller] no new messages (last: {last_ts[:19]})", flush=True)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[poller] stopped", flush=True)
        sys.exit(0)
