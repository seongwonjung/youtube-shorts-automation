# Discord 원격 제어 에이전트 설계 스펙

> Claude Code `/loop` 기반 · Discord 입출력 · 로컬 PC 원격 제어

**작성일:** 2026-04-17  
**상태:** 승인됨

---

## 목표

Discord 채널을 원격 제어 인터페이스로 사용하여, 휴대폰에서 보낸 메시지를 로컬 PC의 Claude Code가 감지하고 작업을 수행한 뒤 결과를 Discord로 답장하는 시스템.

---

## 제약 조건

| 항목 | 결정 |
|------|------|
| 실행 방식 | Claude Code `/loop` 스킬 |
| 인증 | 없음 (채널에 메시지 오면 모두 처리) |
| 루프 간격 | 30초 |
| 작업 범위 | 범용 (파일 읽기/수정, 터미널, git 등 Claude Code가 할 수 있는 모든 것) |
| PC 상태 | 로컬 PC 켜짐 + Claude Code 세션 유지 필요 |

---

## 1. 아키텍처

```
[휴대폰]
  Discord 앱에서 #일반 채널에 메시지 입력
        │
        ▼
[Discord 채널]  ←──────────────────────────────┐
        │                                      │
        ▼                                      │
[로컬 PC - Claude Code /loop]                  │
  1. discord read-messages 호출                │
  2. state.json의 last_message_id와 비교        │
  3. 새 메시지 있으면:                          │
     a. 메시지 내용을 작업 지시로 해석           │
     b. 파일 읽기/수정, 터미널, git 등 수행      │
     c. 결과를 Discord로 전송 ─────────────────┘
  4. state.json 업데이트
  5. 30초 후 다시 1번으로
```

---

## 2. 파일 구조

```
discord_agent/
├── state.json      # 상태 추적 (last_message_id)
└── prompt.md       # /loop 시스템 프롬프트
```

### 2.1 `discord_agent/state.json`

```json
{
  "last_message_id": "0"
}
```

- `last_message_id`: 마지막으로 처리한 Discord 메시지 ID
- 초기값 `"0"` → 첫 루프 실행 시 채널의 현재 최신 메시지 ID를 읽어 state.json에 덮어쓴다 (과거 메시지 재실행 방지). 이후부터는 해당 ID 이후 메시지만 처리.

### 2.2 `discord_agent/prompt.md`

루프마다 실행할 지시문. 내용:

```
1. discord_agent/state.json을 읽어 last_message_id를 확인한다.
2. Discord #일반 채널의 최근 메시지를 읽는다.
3. last_message_id가 "0"이면 현재 최신 메시지 ID를 state.json에 저장하고 종료한다.
4. last_message_id보다 큰 ID의 새 메시지가 있으면:
   a. Discord에 "⚙️ 작업 시작: [메시지 내용]"을 전송한다.
   b. 메시지를 작업 지시로 해석하여 수행한다.
   c. 결과를 Discord에 전송한다 (성공: ✅, 실패: ❌, 최대 1800자).
   d. state.json의 last_message_id를 처리한 최신 메시지 ID로 업데이트한다.
5. 새 메시지가 없으면 아무것도 하지 않는다.
```

---

## 3. 메시지 처리 흐름

```
새 메시지 감지
      │
      ▼
작업 시작 알림 전송
  → "⚙️ 작업 시작: [메시지 내용]"
      │
      ▼
메시지를 자연어 지시로 해석하여 작업 수행
  예) "src/pipeline/runner.py 보여줘" → Read 도구
  예) "git status 확인해줘"           → Bash 도구
  예) "README.md 요약해줘"            → Read + 텍스트 응답
      │
      ▼
결과를 Discord로 전송
  성공: "✅ 완료\n```\n{결과}\n```"
  실패: "❌ 에러\n```\n{에러 메시지}\n```"
      │
      ▼
state.json의 last_message_id 업데이트
```

**출력 길이 제한**: Discord 메시지 2000자 제한으로 인해 결과가 길면 앞 1800자만 전송하고 `... (이하 생략)` 표시.

---

## 4. 실행 방법

```bash
# Claude Code 터미널에서 한 번 입력하면 루프 시작
/loop 30s discord_agent/prompt.md 내용을 읽고 실행해줘
```

**중단**: Claude Code 세션 종료 또는 `Ctrl+C`

---

## 5. Discord MCP 연동

`.mcp.json`에 이미 설정된 Discord MCP 사용:

```json
{
  "mcpServers": {
    "discord": {
      "env": {
        "DISCORD_CHANNEL_ID": "1494388038229430353"
      }
    }
  }
}
```

사용 도구:
- `mcp__discord__read-messages` — 채널 메시지 읽기
- `mcp__discord__send-message` — 채널에 답장 전송

---

## 6. 구현 항목

1. `discord_agent/state.json` 생성 (초기 `last_message_id: "0"`)
2. `discord_agent/prompt.md` 작성 — 루프 동작 지시문
