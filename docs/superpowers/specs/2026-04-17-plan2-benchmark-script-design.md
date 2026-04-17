# Plan 2: BenchmarkStage + ScriptStage 설계 스펙

**작성일:** 2026-04-17  
**상태:** 검토 대기  
**브랜치:** `feat/plan2-benchmark-script` (off `feat/plan1-core-harness`)

---

## 목표

스텁으로만 존재하던 `BenchmarkStage`와 `ScriptStage`를 실제 동작하도록 구현한다.

- **BenchmarkStage:** YouTube 영상 URL들을 분석해 `ctx.benchmark`에 결과 저장
- **ScriptStage:** benchmark 결과와 topic을 바탕으로 Claude가 스크립트 생성, `ctx.script`에 저장

Perplexity 없음. Whisper 없음 (ElevenLabs가 타임스탬프 포함 자막 반환).

---

## 아키텍처

```
BenchmarkStage
  │
  ├─ YouTube Data API v3 (video info, comments)
  │    └─ google-api-python-client (이미 설치됨)
  ├─ youtube-transcript-api (자막/transcript, 인증 불필요)
  │
  └─ Claude API (claude-sonnet-4-6)
       └─ 수집 데이터 → BenchmarkResult JSON 분석

ScriptStage
  │
  └─ Claude API (claude-sonnet-4-6)
       └─ BenchmarkResult + topic + channel config → ScriptResult JSON
```

---

## BenchmarkStage

### 입력

- `ctx.urls`: YouTube 영상 URL 목록 (1~3개)
- `ctx.topic`: 만들 영상 주제

### 처리 흐름

1. 각 URL에서 video_id 추출
2. YouTube Data API v3로 수집:
   - 영상 제목, 설명, 조회수, 좋아요 수 (`videos.list`)
   - 상위 댓글 50개 (`commentThreads.list`)
3. youtube-transcript-api로 자막(transcript) 수집
4. 수집된 데이터 전체를 Claude에 전달 → BenchmarkResult JSON 반환
5. `ctx.benchmark` 저장

### 새로 필요한 것

- `youtube_api_key`: YouTube Data API v3 키 (Settings에 추가)
- `youtube-transcript-api` 패키지 (pyproject.toml에 추가)

### Claude 프롬프트 전략

- system: 역할 정의 + BenchmarkResult JSON 스키마 (캐시 가능)
- user: 수집된 YouTube 데이터 (영상별)
- 응답: BenchmarkResult JSON

---

## ScriptStage

### 입력

- `ctx.benchmark`: BenchmarkResult
- `ctx.topic`: 만들 영상 주제
- `ctx.channel`: 채널 설정 (visual_style_presets, subtitle_style 등)
- `ctx.duration`: 목표 길이(초)

### 처리 흐름

1. benchmark 분석 결과 + topic → Claude에 전달
2. Claude가 ScriptResult JSON 반환:
   - title, hook
   - scenes: 각 씬별 narration, image_prompt, duration_sec, caption
   - cta, thumbnail_prompt, youtube_meta
3. `ctx.script` 저장

### Claude 프롬프트 전략

- system: 역할 정의 + ScriptResult JSON 스키마 (캐시 가능)
- user: benchmark 결과 + topic + 채널 스타일 설정
- 응답: ScriptResult JSON

---

## 설정 변경

### Settings (src/config/settings.py)

```python
youtube_api_key: str  # YouTube Data API v3
```

### .env.example

```
YOUTUBE_API_KEY=your-youtube-data-api-key
```

### pyproject.toml

```toml
"youtube-transcript-api>=0.6.0",
```

---

## 테스트 전략

- `tests/unit/test_benchmark_stage.py`: YouTube 클라이언트 + Claude 클라이언트 mock
- `tests/unit/test_script_stage.py`: Claude 클라이언트 mock
- 검증: BenchmarkResult/ScriptResult가 ctx에 올바르게 저장되는지

---

## 파일 구성

```
src/stages/benchmark.py     ← 실제 구현으로 교체
src/stages/script.py        ← 실제 구현으로 교체
src/services/youtube.py     ← YouTube API 클라이언트 (신규)
src/services/claude.py      ← Claude API 클라이언트 (신규)
src/config/settings.py      ← youtube_api_key 추가
.env.example                ← YOUTUBE_API_KEY 추가
pyproject.toml              ← youtube-transcript-api 추가
tests/unit/test_benchmark_stage.py  ← 신규
tests/unit/test_script_stage.py     ← 신규
```

---

## 범위 밖 (Plan 3 이후)

- TTS (ElevenLabs) — Plan 3
- 이미지/영상 생성 — Plan 4
- 업로드 — Plan 5
