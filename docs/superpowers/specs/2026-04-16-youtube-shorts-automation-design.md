# YouTube Shorts 자동화 시스템 설계 스펙

> BaseStage 클래스 기반 파이프라인 · 체크포인트 재시작 · 제한적 병렬 처리 · uv · Docker 호환

**작성일:** 2026-04-16  
**상태:** 승인됨

---

## 결정된 제약 조건

| 항목 | 결정 |
|------|------|
| 파이프라인 실패 처리 | 체크포인트 기반 재시작 (완료 스테이지 보존) |
| 실행 환경 | 로컬 PC + 서버/Docker 호환 |
| 씬 병렬 처리 | 제한적 병렬 (asyncio Semaphore, 기본 N=3) |
| 패키지 관리 | uv + pyproject.toml |
| 멀티채널 동시 실행 | 추후 확장 (현재는 단일 채널) |

---

## 1. 프로젝트 구조

```
youtube-shorts-automation/
├── run.py                          # 진입점
├── pyproject.toml                  # uv 관리
├── .env.example                    # API 키 템플릿
├── Dockerfile
├── docker-compose.yml
│
├── src/
│   ├── cli/
│   │   └── main.py                 # argparse CLI 정의
│   │
│   ├── pipeline/
│   │   ├── runner.py               # PipelineRunner
│   │   ├── context.py              # PipelineContext dataclass
│   │   └── state.py                # CheckpointManager
│   │
│   ├── stages/
│   │   ├── base.py                 # BaseStage 추상 클래스
│   │   ├── benchmark.py            # ① BenchmarkStage
│   │   ├── script.py               # ② ScriptStage
│   │   ├── tts.py                  # ③ TTSStage
│   │   ├── storyboard.py           # ④ StoryboardStage
│   │   ├── image_video.py          # ⑤ ImageVideoStage
│   │   ├── edit.py                 # ⑥ EditStage
│   │   ├── thumbnail.py            # ⑦ ThumbnailStage
│   │   └── upload.py               # ⑧ UploadStage
│   │
│   ├── services/                   # 외부 API 래퍼 (교체 가능)
│   │   ├── claude.py
│   │   ├── youtube.py
│   │   ├── elevenlabs.py
│   │   ├── whisper.py
│   │   ├── flux.py
│   │   ├── kling.py
│   │   ├── perplexity.py
│   │   └── ffmpeg.py
│   │
│   └── config/
│       ├── settings.py             # 전역 설정 (pydantic-settings)
│       └── channel.py              # ChannelConfig 로더
│
├── channels/
│   └── channel_a/
│       └── config.json
│
├── runs/                           # 각 실행 결과 (.gitignore)
│   └── channel_a/
│       └── {run_id}/
│           ├── pipeline_state.json
│           ├── benchmark.json
│           ├── script.json
│           ├── scene_01.mp3
│           └── ...
│
├── cache/                          # 벤치마킹 캐시 (.gitignore)
│
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

---

## 2. 기술 스택

| 역할 | 선택 | 이유 |
|------|------|------|
| Python 버전 | 3.12 | 최신 안정, uv 지원 |
| 패키지 관리 | uv | 속도, lockfile, Docker 친화 |
| CLI | argparse (stdlib) | 의존성 없음, 충분 |
| 설정 | pydantic-settings | .env 파싱 + 타입 검증 |
| 데이터 모델 | pydantic v2 | script.json 검증, 직렬화 |
| 비동기 | asyncio (stdlib) | 병렬 씬 처리 |
| HTTP | httpx | async 지원, 테스트 용이 |
| 로깅 | loguru | 컬러 출력, 파일 저장 |
| 컨테이너 | Docker + compose | 서버 배포 |

**외부 API:**
- Claude API (anthropic SDK) — 분석/대본/프롬프트 강화
- YouTube Data API v3 — 자막/댓글 수집, 업로드
- ElevenLabs API — TTS
- OpenAI Whisper — SRT 생성 (로컬 실행)
- Flux API — 이미지 생성
- Kling AI API — 이미지→영상
- Perplexity API — 팩트체크/리서치
- FFmpeg — 편집 (로컬 바이너리)

---

## 3. 하네스 핵심 설계

### 3.1 BaseStage 인터페이스

```python
# src/stages/base.py
class BaseStage(ABC):
    name: str       # 스테이지 식별자 (예: "benchmark")
    stage_no: int   # 순서 번호 (1~8)

    @abstractmethod
    async def run(self, ctx: PipelineContext) -> PipelineContext:
        """실행: ctx를 받아 결과를 채운 ctx를 반환"""

    def can_skip(self, ctx: PipelineContext) -> bool:
        """이미 완료됐는지 확인 — 기본: completed_stages 목록 확인"""
        return self.name in ctx.completed_stages
```

### 3.2 PipelineContext

모든 중간 결과를 하나의 Pydantic 모델로 관리. JSON 직렬화로 체크포인트 저장/로드.

```python
# src/pipeline/context.py
class PipelineContext(BaseModel):
    # 실행 메타
    run_id:   str          # "20260416_143022_abc123"
    run_dir:  Path         # runs/channel_a/{run_id}/
    channel:  ChannelConfig

    # CLI 입력
    urls:     list[str]
    topic:    str
    style:    str | None
    duration: int = 60

    # 체크포인트
    completed_stages: list[str] = []

    # 스테이지별 결과 (점진적으로 채워짐)
    benchmark:   BenchmarkResult   | None = None
    script:      ScriptResult      | None = None
    tts:         TTSResult         | None = None
    storyboard:  StoryboardResult  | None = None
    image_video: ImageVideoResult  | None = None
    edit:        EditResult        | None = None
    thumbnail:   ThumbnailResult   | None = None
    upload:      UploadResult      | None = None
```

### 3.3 PipelineRunner 실행 흐름

```python
# src/pipeline/runner.py
class PipelineRunner:
    stages = [
        BenchmarkStage(),   # ①
        ScriptStage(),      # ②
        TTSStage(),         # ③
        StoryboardStage(),  # ④
        ImageVideoStage(),  # ⑤
        EditStage(),        # ⑥
        ThumbnailStage(),   # ⑦
        UploadStage(),      # ⑧
    ]

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        for stage in self.stages:
            if stage.can_skip(ctx):
                logger.info(f"⏩ [{stage.name}] 스킵 (이미 완료)")
                continue

            logger.info(f"▶ [{stage.name}] 시작")
            ctx = await self._run_with_retry(stage, ctx)
            self.checkpoint.save(ctx)                    # 즉시 저장
            logger.info(f"✅ [{stage.name}] 완료")

        return ctx

    async def _run_with_retry(self, stage, ctx, max_retries=3):
        for attempt in range(max_retries):
            try:
                return await stage.run(ctx)
            except Exception as e:
                if attempt == max_retries - 1:
                    ctx.last_error = str(e)
                    self.checkpoint.save(ctx)            # 실패 상태 저장
                    raise
                wait = 2 ** attempt                      # 지수 백오프
                logger.warning(f"재시도 {attempt+1}/{max_retries} ({wait}s 후)")
                await asyncio.sleep(wait)
```

### 3.4 CheckpointManager

```python
# src/pipeline/state.py
class CheckpointManager:
    def save(self, ctx: PipelineContext) -> None:
        """ctx → pipeline_state.json 저장"""
        path = ctx.run_dir / "pipeline_state.json"
        path.write_text(ctx.model_dump_json(indent=2))

    def load(self, run_dir: Path) -> PipelineContext:
        """pipeline_state.json → ctx 복원"""
        path = run_dir / "pipeline_state.json"
        return PipelineContext.model_validate_json(path.read_text())
```

**pipeline_state.json 구조:**
```json
{
  "run_id": "20260416_143022_abc123",
  "channel": "channel_a",
  "topic": "카페인 과다복용 부작용 5가지",
  "completed_stages": ["benchmark", "script", "tts"],
  "current_stage": "storyboard",
  "status": "in_progress",
  "last_error": null,
  "created_at": "2026-04-16T14:30:22Z",
  "updated_at": "2026-04-16T14:45:11Z"
}
```

---

## 4. CLI 인터페이스

```bash
# 신규 실행
python run.py \
  --urls "https://youtube.com/shorts/xxx" "https://youtube.com/shorts/yyy" \
  --topic "카페인 과다복용 부작용 5가지" \
  --channel channel_a \
  --style "dark cinematic"        # 선택사항
  --duration 60                   # 선택사항

# 실패 후 재시작
python run.py --resume runs/channel_a/20260416_143022_abc123

# 특정 스테이지부터 강제 재실행
python run.py --resume runs/channel_a/20260416_143022_abc123 --from-stage tts
```

---

## 5. 병렬 처리 설계

씬이 많은 스테이지(③ TTS, ④ Storyboard, ⑤ ImageVideo)는 `asyncio.Semaphore`로 N개씩 병렬 처리:

```python
# src/stages/image_video.py
class ImageVideoStage(BaseStage):
    name = "image_video"

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        concurrency = ctx.channel.concurrency  # 기본: 3
        semaphore = asyncio.Semaphore(concurrency)

        async def process_scene(scene):
            async with semaphore:
                # 씬 파일이 이미 있으면 스킵 (씬 단위 체크포인트)
                if self._scene_done(ctx.run_dir, scene.scene_no):
                    return self._load_scene(ctx.run_dir, scene.scene_no)
                img  = await self.flux.generate(scene.enhanced_prompt)
                clip = await self.kling.image_to_video(img, scene.duration_sec)
                return SceneMedia(scene_no=scene.scene_no, image=img, clip=clip)

        results = await asyncio.gather(
            *[process_scene(s) for s in ctx.storyboard.scenes]
        )
        ctx.image_video = ImageVideoResult(scenes=results)
        return ctx
```

씬 단위 체크포인트: `scene_03.png` 파일 존재 여부로 씬 완료 판단. 스테이지 전체 재실행 없이 실패한 씬만 재생성.

---

## 6. 설정 시스템 — 3계층

### 계층 1: .env (API 키, 민감 정보)
```env
ANTHROPIC_API_KEY=sk-ant-...
ELEVENLABS_API_KEY=...
FLUX_API_KEY=...
KLING_API_KEY=...
PERPLEXITY_API_KEY=...
YOUTUBE_CLIENT_SECRET_PATH=secrets/youtube_client_secret.json
```

### 계층 2: settings.py (전역 동작)
```python
class Settings(BaseSettings):
    max_retries: int = 3
    retry_backoff_base: int = 2
    default_concurrency: int = 3
    default_duration: int = 60
    log_level: str = "INFO"
    model_config = SettingsConfigDict(env_file=".env")
```

### 계층 3: channels/{name}/config.json (채널별)
```json
{
  "channel_id": "channel_a",
  "voice_id": "elevenlabs_voice_id",
  "concurrency": 3,
  "visual_style_presets": {
    "default": "dark cinematic, moody lighting, Korean aesthetic"
  },
  "subtitle_style": {
    "font": "NanumGothicBold",
    "size": 52,
    "color": "white",
    "outline": 3,
    "position": "bottom_third"
  },
  "bgm_enabled": true,
  "bgm_volume": 0.15
}
```

**우선순위:** 채널 config > settings.py > .env 기본값

---

## 7. 에러 처리 전략

| 서비스 | 재시도 | Rate limit | 최종 실패 시 |
|--------|--------|------------|-------------|
| Claude API | 3회 | 429 → 60s 대기 | 스테이지 실패 저장 |
| ElevenLabs | 3회 | 지수 백오프 | 씬 단위 실패 기록 |
| Flux / Kling | 3회 | 지수 백오프 | 씬 단위 실패 기록 |
| YouTube API | 1회 | — | 수동 재업로드 안내 출력 |

모든 실패는 `pipeline_state.json`의 `last_error`에 기록. `--resume`으로 재시작 가능.

---

## 8. 테스트 전략

```
tests/
  unit/
    test_checkpoint.py       # CheckpointManager 저장/로드/재시작 로직
    test_pipeline_runner.py  # can_skip 판단, 스테이지 순서 보장
    test_config.py           # 채널 config 로드, 우선순위 병합
  integration/
    test_stages.py           # 각 스테이지를 mock service로 실행
    test_resume.py           # 3단계 완료 → 실패 → resume 시나리오
  e2e/
    test_full_pipeline.py    # 전체 파이프라인 (실제 API, CI에서는 skip)
```

핵심 테스트 시나리오:
1. `completed_stages=["benchmark", "script", "tts"]` 상태에서 `--resume` 시 `storyboard`부터 실행
2. 씬 12개 중 씬 3번만 실패한 경우, 씬 3번만 재생성
3. Claude API 429 에러 → 60s 대기 후 재시도 → 성공

---

## 9. Docker 배포

```dockerfile
# Dockerfile
FROM python:3.12-slim
RUN pip install uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen
COPY src/ src/
COPY channels/ channels/
VOLUME ["/app/runs", "/app/cache", "/app/secrets"]
ENTRYPOINT ["uv", "run", "python", "run.py"]
```

환경변수는 `.env` 파일 또는 docker-compose의 `environment:` 섹션으로 주입.  
`runs/`, `cache/`, `secrets/` 는 볼륨으로 마운트하여 컨테이너 재시작 후에도 데이터 유지.

---

## 10. 구현 순서

1. **프로젝트 스캐폴딩** — uv init, pyproject.toml, 디렉토리 구조
2. **하네스 코어** — BaseStage, PipelineContext, PipelineRunner, CheckpointManager
3. **① BenchmarkStage** — YouTube API + Claude 분석 (전략 리포트 + 사람 승인)
4. **② ScriptStage** — Claude 대본 생성
5. **③ TTSStage** — ElevenLabs + Whisper
6. **④ StoryboardStage** — Claude 프롬프트 강화
7. **⑤ ImageVideoStage** — Flux + Kling (병렬 처리)
8. **⑥ EditStage** — FFmpeg 편집
9. **⑦ ThumbnailStage** — Flux
10. **⑧ UploadStage** — YouTube Data API v3
11. **Docker 설정** — Dockerfile + docker-compose.yml
