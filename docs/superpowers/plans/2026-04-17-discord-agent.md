# Discord 원격 제어 에이전트 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Discord 채널을 입출력 인터페이스로 사용하여, 휴대폰에서 보낸 메시지를 로컬 PC의 Claude Code `/loop`가 감지하고 작업을 수행한 뒤 결과를 Discord로 답장하는 원격 제어 시스템을 구축한다.

**Architecture:** Claude Code `/loop` 스킬이 30초마다 Discord 채널을 폴링한다. `discord_agent/state.json`에 저장된 `last_message_id`와 비교하여 새 메시지만 처리하고, 결과를 Discord로 전송한 뒤 상태를 업데이트한다.

**Tech Stack:** Claude Code `/loop` 스킬, Discord MCP (`mcp__discord__read-messages`, `mcp__discord__send-message`), 로컬 JSON 파일 상태 관리

---

## 파일 구조

| 파일 | 역할 |
|------|------|
| `discord_agent/state.json` | `last_message_id` 저장 — 이미 처리한 메시지 재실행 방지 |
| `discord_agent/prompt.md` | `/loop`에 매 반복마다 실행할 지시문 |

---

### Task 1: state.json 생성

**Files:**
- Create: `discord_agent/state.json`

- [ ] **Step 1: 디렉토리 및 파일 생성**

```bash
mkdir -p discord_agent
```

`discord_agent/state.json` 내용:
```json
{
  "last_message_id": "0"
}
```

`"0"`은 초기값. 첫 루프 실행 시 현재 채널의 최신 메시지 ID로 덮어써진다 (과거 메시지 재실행 방지).

- [ ] **Step 2: 파일 확인**

```bash
cat discord_agent/state.json
```

Expected output:
```json
{
  "last_message_id": "0"
}
```

- [ ] **Step 3: Commit**

```bash
git add discord_agent/state.json
git commit -m "feat: add discord agent state file"
```

---

### Task 2: prompt.md 생성

**Files:**
- Create: `discord_agent/prompt.md`

- [ ] **Step 1: prompt.md 작성**

`discord_agent/prompt.md` 내용:
```markdown
아래 절차를 정확히 따른다.

## 절차

1. `discord_agent/state.json`을 읽어 `last_message_id` 값을 확인한다.

2. Discord `#일반` 채널의 최근 메시지를 `mcp__discord__read-messages`로 읽는다.

3. `last_message_id`가 `"0"`이면 (첫 실행):
   - 읽은 메시지 중 가장 최신 메시지의 ID를 `discord_agent/state.json`에 저장한다.
   - `mcp__discord__send-message`로 `#일반`에 `"✅ Discord 에이전트가 시작되었습니다. 명령을 입력하세요."` 를 전송한다.
   - 절차를 종료한다 (과거 메시지 실행하지 않음).

4. 읽은 메시지 중 `last_message_id`보다 큰 ID를 가진 메시지를 시간순으로 정렬하여 처리 대상으로 삼는다.

5. 처리 대상 메시지가 없으면 아무것도 하지 않고 종료한다.

6. 처리 대상 메시지가 있으면 각 메시지를 순서대로 처리한다:

   a. `mcp__discord__send-message`로 `#일반`에 다음을 전송한다:
      ```
      ⚙️ 작업 시작: [메시지 내용]
      ```

   b. 메시지 내용을 작업 지시로 해석하여 수행한다.
      - 파일 읽기/수정, 터미널 명령, git 작업 등 Claude Code가 할 수 있는 모든 작업을 수행한다.
      - 작업 중 에러가 발생하면 에러 내용을 기록해 둔다.

   c. 작업 완료 후 결과를 `mcp__discord__send-message`로 `#일반`에 전송한다.
      - 성공 시: `"✅ 완료\n\`\`\`\n{결과}\n\`\`\`"`
      - 실패 시: `"❌ 에러\n\`\`\`\n{에러 메시지}\n\`\`\`"`
      - 결과가 1800자를 초과하면 앞 1800자만 전송하고 `\n... (이하 생략)`을 붙인다.

   d. `discord_agent/state.json`의 `last_message_id`를 방금 처리한 메시지의 ID로 업데이트한다.

7. 모든 처리 대상 메시지를 처리했으면 종료한다.
```

- [ ] **Step 2: 파일 확인**

```bash
cat discord_agent/prompt.md
```

Expected: 위 내용이 그대로 출력됨.

- [ ] **Step 3: Commit**

```bash
git add discord_agent/prompt.md
git commit -m "feat: add discord agent loop prompt"
```

---

### Task 3: 에이전트 실행 및 동작 검증

**Files:**
- 없음 (실행 검증만)

- [ ] **Step 1: 루프 시작**

Claude Code 터미널에서 실행:
```
/loop 30s discord_agent/prompt.md 파일을 읽고 절차를 따라 실행해줘
```

- [ ] **Step 2: 초기화 확인**

Discord `#일반` 채널에 다음 메시지가 전송되는지 확인:
```
✅ Discord 에이전트가 시작되었습니다. 명령을 입력하세요.
```

`discord_agent/state.json`에 `last_message_id`가 `"0"`이 아닌 실제 메시지 ID로 업데이트되었는지 확인:
```bash
cat discord_agent/state.json
```
Expected: `"last_message_id"` 값이 숫자 문자열 (예: `"1494391223484678154"`)

- [ ] **Step 3: 명령 테스트 — 파일 읽기**

휴대폰(또는 다른 Discord 클라이언트)에서 `#일반` 채널에 다음 메시지 전송:
```
README.md 내용 보여줘
```

30초 이내에 Discord에서 다음 응답 확인:
```
⚙️ 작업 시작: README.md 내용 보여줘
```
이후:
```
✅ 완료
```
(README.md 내용 포함)

- [ ] **Step 4: 명령 테스트 — 터미널 명령**

`#일반` 채널에 다음 메시지 전송:
```
git log --oneline -5
```

30초 이내에 Discord에서 최근 5개 커밋 내역이 답장으로 오는지 확인.

- [ ] **Step 5: 루프 중단 방법 확인**

Claude Code에서 `Ctrl+C` 또는 세션 종료로 루프가 중단됨을 확인.

---

## 실행 요약

에이전트 시작:
```
/loop 30s discord_agent/prompt.md 파일을 읽고 절차를 따라 실행해줘
```

에이전트 중단: Claude Code 세션 종료 또는 `Ctrl+C`
