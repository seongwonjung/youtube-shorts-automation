# YouTube Shorts 자동화 — Plan 1: Core Harness 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 파이프라인 하네스 코어 구현 — 체크포인트 재시작, 8개 스텁 스테이지가 end-to-end로 동작하는 기반 완성

**Architecture:** BaseStage ABC + PipelineRunner가 스테이지를 순서대로 실행하며 각 완료 후 CheckpointManager가 PipelineContext를 JSON으로 저장. 재시작 시 completed_stages 목록을 보고 완료된 스테이지를 스킵.

**Tech Stack:** Python 3.12, uv, pydantic v2, pydantic-settings, asyncio, loguru, pytest, pytest-asyncio, pytest-mock

---

## 이 계획의 범위

이 계획(Plan 1)은 **하네스 코어와 스텁 스테이지**만 구현합니다.
실제 API 호출은 이후 계획들에서 구현됩니다:

- **Plan 2:** BenchmarkStage + ScriptStage (Claude + YouTube + Perplexity API)
- **Plan 3:** TTSStage + StoryboardStage (ElevenLabs + Whisper + Claude)
- **Plan 4:** ImageVideoStage + EditStage (Flux + Kling + FFmpeg)
- **Plan 5:** ThumbnailStage + UploadStage + Docker 완성

---

## 파일 구조

**생성:**
```
pyproject.toml
.env.example
run.py
src/__init__.py
src/cli/__init__.py
src/cli/main.py
src/pipeline/__init__.py
src/pipeline/context.py
src/pipeline/state.py
src/pipeline/runner.py
src/stages/__init__.py
src/stages/base.py
src/stages/benchmark.py       (스텁)
src/stages/script.py          (스텁)
src/stages/tts.py             (스텁)
src/stages/storyboard.py      (스텁)
src/stages/image_video.py     (스텁)
src/stages/edit.py            (스텁)
src/stages/thumbnail.py       (스텁)
src/stages/upload.py          (스텁)
src/services/__init__.py
src/config/__init__.py
src/config/settings.py
src/config/channel.py
channels/channel_a/config.json
tests/__init__.py
tests/unit/__init__.py
tests/unit/test_config.py
tests/unit/test_checkpoint.py
tests/unit/test_pipeline_runner.py
tests/unit/test_cli.py
tests/integration/__init__.py
tests/integration/test_resume.py
Dockerfile
docker-compose.yml
```

---

### Task 1: uv 프로젝트 초기화 + 의존성 정의

**Files:**
- Create: `pyproject.toml`

- [ ] **Step 1: pyproject.toml 작성**

```toml
[project]
name = "youtube-shorts-automation"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "anthropic>=0.40.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",
    "httpx>=0.27.0",
    "loguru>=0.7.0",
    "google-api-python-client>=2.150.0",
    "google-auth-httplib2>=0.2.0",
    "google-auth-oauthlib>=1.2.0",
    "elevenlabs>=1.13.0",
    "openai>=1.50.0",
]

[dependency-groups]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-mock>=3.14.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 2: 의존성 설치**

```bash
uv sync --dev
```

Expected: `.venv/` 생성, 모든 패키지 설치 완료

- [ ] **Step 3: 디렉토리 구조 생성**

```bash
mkdir -p src/cli src/pipeline src/stages src/services src/config
mkdir -p channels/channel_a
mkdir -p tests/unit tests/integration
touch src/__init__.py src/cli/__init__.py src/pipeline/__init__.py
touch src/stages/__init__.py src/services/__init__.py src/config/__init__.py
touch tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml src/ tests/ channels/
git commit -m "chore: uv 프로젝트 초기화 + 디렉토리 구조"
```

---

### Task 2: 환경 설정 파일

**Files:**
- Create: `.env.example`
- Create: `channels/channel_a/config.json`

- [ ] **Step 1: .env.example 작성**

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
ELEVENLABS_API_KEY=your-key-here
FLUX_API_KEY=your-key-here
KLING_API_KEY=your-key-here
PERPLEXITY_API_KEY=your-key-here
OPENAI_API_KEY=your-key-here
YOUTUBE_CLIENT_SECRET_PATH=secrets/youtube_client_secret.json

MAX_RETRIES=3
RETRY_BACKOFF_BASE=2
DEFAULT_CONCURRENCY=3
DEFAULT_DURATION=60
LOG_LEVEL=INFO
```

- [ ] **Step 2: channels/channel_a/config.json 작성**

```json
{
  "channel_id": "channel_a",
  "youtube_channel_id": "UCxxxxxxxxxxxxxxxxxxxxxxx",
  "voice_id": "your-elevenlabs-voice-id",
  "concurrency": 3,
  "visual_style_presets": {
    "default": "dark cinematic, moody lighting, Korean aesthetic",
    "bright": "minimal white, clean modern, bright lighting",
    "retro": "film grain, vintage color grading, nostalgic"
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

- [ ] **Step 3: Commit**

```bash
git add .env.example channels/channel_a/config.json
git commit -m "chore: 환경 설정 파일 + 채널 config 추가"
```

---

### Task 3: ChannelConfig 모델

**Files:**
- Create: `src/config/channel.py`
- Create: `tests/unit/test_config.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/unit/test_config.py`:
```python
import json
from pathlib import Path
import pytest
from src.config.channel import ChannelConfig, SubtitleStyle, load_channel_config


def test_channel_config_loads_from_json(tmp_path):
    config_dir = tmp_path / "channels" / "test_ch"
    config_dir.mkdir(parents=True)
    config = {
        "channel_id": "test_ch",
        "youtube_channel_id": "UCtest",
        "voice_id": "voice_123",
        "concurrency": 4,
        "visual_style_presets": {"default": "dark cinematic"},
        "subtitle_style": {
            "font": "NanumGothicBold",
            "size": 52,
            "color": "white",
            "outline": 3,
            "position": "bottom_third",
        },
        "bgm_enabled": True,
        "bgm_volume": 0.15,
    }
    (config_dir / "config.json").write_text(json.dumps(config))

    ch = load_channel_config("test_ch", channels_dir=tmp_path / "channels")

    assert ch.channel_id == "test_ch"
    assert ch.voice_id == "voice_123"
    assert ch.concurrency == 4
    assert ch.subtitle_style.font == "NanumGothicBold"
    assert ch.bgm_volume == 0.15


def test_channel_config_defaults():
    ch = ChannelConfig(channel_id="x", voice_id="v")
    assert ch.concurrency == 3
    assert ch.bgm_enabled is True
    assert ch.bgm_volume == 0.15
    assert isinstance(ch.subtitle_style, SubtitleStyle)
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.config.channel'`

- [ ] **Step 3: ChannelConfig 구현**

`src/config/channel.py`:
```python
from pathlib import Path
from pydantic import BaseModel


class SubtitleStyle(BaseModel):
    font: str = "NanumGothicBold"
    size: int = 52
    color: str = "white"
    outline: int = 3
    position: str = "bottom_third"


class ChannelConfig(BaseModel):
    channel_id: str
    youtube_channel_id: str = ""
    voice_id: str
    concurrency: int = 3
    visual_style_presets: dict[str, str] = {}
    subtitle_style: SubtitleStyle = SubtitleStyle()
    bgm_enabled: bool = True
    bgm_volume: float = 0.15


def load_channel_config(
    channel_name: str,
    channels_dir: Path = Path("channels"),
) -> ChannelConfig:
    path = channels_dir / channel_name / "config.json"
    return ChannelConfig.model_validate_json(path.read_text(encoding="utf-8"))
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/config/channel.py tests/unit/test_config.py
git commit -m "feat: ChannelConfig 모델 + load_channel_config"
```

---

### Task 4: Settings (전역 설정)

**Files:**
- Create: `src/config/settings.py`
- Modify: `tests/unit/test_config.py`

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/unit/test_config.py` 하단에 추가:
```python
from src.config.settings import Settings


def _base_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-test")
    monkeypatch.setenv("FLUX_API_KEY", "flux-test")
    monkeypatch.setenv("KLING_API_KEY", "kling-test")
    monkeypatch.setenv("PERPLEXITY_API_KEY", "perp-test")
    monkeypatch.setenv("OPENAI_API_KEY", "oai-test")


def test_settings_loads_from_env(monkeypatch):
    _base_env(monkeypatch)

    settings = Settings()

    assert settings.anthropic_api_key == "sk-test"
    assert settings.max_retries == 3
    assert settings.default_concurrency == 3


def test_settings_override_defaults(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.setenv("MAX_RETRIES", "5")
    monkeypatch.setenv("DEFAULT_CONCURRENCY", "2")

    settings = Settings()

    assert settings.max_retries == 5
    assert settings.default_concurrency == 2
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/unit/test_config.py::test_settings_loads_from_env -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.config.settings'`

- [ ] **Step 3: Settings 구현**

`src/config/settings.py`:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API Keys
    anthropic_api_key: str
    elevenlabs_api_key: str
    flux_api_key: str
    kling_api_key: str
    perplexity_api_key: str
    openai_api_key: str = ""
    youtube_client_secret_path: str = "secrets/youtube_client_secret.json"

    # Pipeline behaviour
    max_retries: int = 3
    retry_backoff_base: int = 2
    default_concurrency: int = 3
    default_duration: int = 60
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: PASS (모든 테스트)

- [ ] **Step 5: Commit**

```bash
git add src/config/settings.py tests/unit/test_config.py
git commit -m "feat: Settings (pydantic-settings) + 테스트"
```

---

### Task 5: PipelineContext 데이터 모델

**Files:**
- Create: `src/pipeline/context.py`
- Create: `tests/unit/test_checkpoint.py` (직렬화 테스트)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/unit/test_checkpoint.py`:
```python
from pathlib import Path
import pytest
from src.pipeline.context import PipelineContext
from src.config.channel import ChannelConfig


def make_test_ctx(tmp_path: Path) -> PipelineContext:
    run_dir = tmp_path / "runs" / "channel_a" / "test_run"
    run_dir.mkdir(parents=True)
    channel = ChannelConfig(channel_id="channel_a", voice_id="v123")
    return PipelineContext(
        run_id="test_run",
        run_dir=run_dir,
        channel_name="channel_a",
        channel=channel,
        urls=["https://youtube.com/shorts/abc"],
        topic="테스트 주제",
        created_at="2026-04-16T00:00:00Z",
        updated_at="2026-04-16T00:00:00Z",
    )


def test_pipeline_context_json_roundtrip(tmp_path):
    ctx = make_test_ctx(tmp_path)

    json_str = ctx.model_dump_json()
    restored = PipelineContext.model_validate_json(json_str)

    assert restored.run_id == ctx.run_id
    assert restored.topic == ctx.topic
    assert restored.channel.voice_id == "v123"
    assert restored.completed_stages == []
    assert restored.benchmark is None


def test_pipeline_context_completed_stages_survives_roundtrip(tmp_path):
    ctx = make_test_ctx(tmp_path)
    ctx.completed_stages.append("benchmark")

    json_str = ctx.model_dump_json()
    restored = PipelineContext.model_validate_json(json_str)

    assert "benchmark" in restored.completed_stages
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/unit/test_checkpoint.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.pipeline.context'`

- [ ] **Step 3: PipelineContext 구현**

`src/pipeline/context.py`:
```python
from __future__ import annotations
from pathlib import Path
from pydantic import BaseModel
from src.config.channel import ChannelConfig


# --- Benchmark ---

class FactCheckItem(BaseModel):
    claim: str
    verified: bool
    source: str


class SubtitleStyleInfo(BaseModel):
    position: str = "bottom_third"
    emphasis: str = ""


class BenchmarkResult(BaseModel):
    hook_pattern: str = ""
    story_structure: str = ""
    tone: str = ""
    pacing: str = "medium"
    visual_style: str = ""
    transition_style: str = "cut"
    bgm_present: bool = False
    bgm_style: str = ""
    subtitle_style: SubtitleStyleInfo = SubtitleStyleInfo()
    positive_from_comments: list[str] = []
    negative_from_comments: list[str] = []
    fact_check_results: list[FactCheckItem] = []
    additional_data: list[str] = []
    recommended_format: str = "list"
    recommended_duration: int = 60
    strategy_summary: str = ""


# --- Script ---

class Scene(BaseModel):
    scene_no: int
    narration: str
    image_prompt: str
    duration_sec: int
    caption: str


class YouTubeMeta(BaseModel):
    title: str = ""
    description: str = ""
    tags: list[str] = []


class ScriptResult(BaseModel):
    title: str = ""
    hook: str = ""
    scenes: list[Scene] = []
    cta: str = ""
    thumbnail_prompt: str = ""
    youtube_meta: YouTubeMeta = YouTubeMeta()


# --- TTS ---

class SceneTTS(BaseModel):
    scene_no: int
    audio_path: str   # run_dir 기준 상대 경로
    srt_path: str


class TTSResult(BaseModel):
    scenes: list[SceneTTS] = []
    voice_id: str = ""


# --- Storyboard ---

class EnhancedScene(BaseModel):
    scene_no: int
    enhanced_prompt: str
    negative_prompt: str


class StoryboardResult(BaseModel):
    scenes: list[EnhancedScene] = []
    visual_style: str = ""


# --- ImageVideo ---

class SceneMedia(BaseModel):
    scene_no: int
    image_path: str   # run_dir 기준 상대 경로
    video_path: str


class ImageVideoResult(BaseModel):
    scenes: list[SceneMedia] = []


# --- Edit / Thumbnail / Upload ---

class EditResult(BaseModel):
    video_path: str = ""     # 예: "final_shorts.mp4"


class ThumbnailResult(BaseModel):
    image_path: str = ""     # 예: "thumbnail.png"


class UploadResult(BaseModel):
    video_id: str = ""
    studio_url: str = ""


# --- PipelineContext ---

class PipelineContext(BaseModel):
    # 실행 메타
    run_id: str
    run_dir: Path
    channel_name: str
    channel: ChannelConfig

    # CLI 입력
    urls: list[str]
    topic: str
    style: str | None = None
    duration: int = 60

    # 체크포인트 상태
    completed_stages: list[str] = []
    current_stage: str | None = None
    status: str = "in_progress"   # "in_progress" | "done" | "failed"
    last_error: str | None = None
    created_at: str = ""
    updated_at: str = ""

    # 스테이지별 결과
    benchmark:   BenchmarkResult   | None = None
    script:      ScriptResult      | None = None
    tts:         TTSResult         | None = None
    storyboard:  StoryboardResult  | None = None
    image_video: ImageVideoResult  | None = None
    edit:        EditResult        | None = None
    thumbnail:   ThumbnailResult   | None = None
    upload:      UploadResult      | None = None
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/unit/test_checkpoint.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/context.py tests/unit/test_checkpoint.py
git commit -m "feat: PipelineContext 데이터 모델 + 직렬화 테스트"
```

---

### Task 6: CheckpointManager

**Files:**
- Create: `src/pipeline/state.py`
- Modify: `tests/unit/test_checkpoint.py`

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/unit/test_checkpoint.py` 하단에 추가:
```python
from src.pipeline.state import CheckpointManager


def test_checkpoint_save_and_load(tmp_path):
    ctx = make_test_ctx(tmp_path)
    ctx.completed_stages = ["benchmark", "script"]

    manager = CheckpointManager()
    manager.save(ctx)

    assert (ctx.run_dir / "pipeline_state.json").exists()

    restored = manager.load(ctx.run_dir)
    assert restored.run_id == ctx.run_id
    assert restored.completed_stages == ["benchmark", "script"]
    assert restored.channel.channel_id == "channel_a"


def test_checkpoint_save_updates_timestamp(tmp_path):
    ctx = make_test_ctx(tmp_path)
    original = ctx.updated_at

    CheckpointManager().save(ctx)
    restored = CheckpointManager().load(ctx.run_dir)

    assert restored.updated_at != original


def test_checkpoint_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        CheckpointManager().load(tmp_path / "nonexistent")
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/unit/test_checkpoint.py::test_checkpoint_save_and_load -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.pipeline.state'`

- [ ] **Step 3: CheckpointManager 구현**

`src/pipeline/state.py`:
```python
from datetime import datetime, timezone
from pathlib import Path
from src.pipeline.context import PipelineContext


class CheckpointManager:
    def save(self, ctx: PipelineContext) -> None:
        ctx.updated_at = datetime.now(timezone.utc).isoformat()
        path = Path(ctx.run_dir) / "pipeline_state.json"
        path.write_text(ctx.model_dump_json(indent=2), encoding="utf-8")

    def load(self, run_dir: Path) -> PipelineContext:
        path = run_dir / "pipeline_state.json"
        if not path.exists():
            raise FileNotFoundError(f"체크포인트 없음: {path}")
        return PipelineContext.model_validate_json(
            path.read_text(encoding="utf-8")
        )
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/unit/test_checkpoint.py -v
```

Expected: PASS (모든 테스트)

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/state.py tests/unit/test_checkpoint.py
git commit -m "feat: CheckpointManager (저장/로드) + 테스트"
```

---

### Task 7: BaseStage 추상 클래스

**Files:**
- Create: `src/stages/base.py`
- Create: `tests/unit/test_pipeline_runner.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/unit/test_pipeline_runner.py`:
```python
import pytest
from pathlib import Path
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext
from src.config.channel import ChannelConfig


def make_ctx(tmp_path: Path) -> PipelineContext:
    run_dir = tmp_path / "runs" / "ch" / "run1"
    run_dir.mkdir(parents=True)
    return PipelineContext(
        run_id="run1",
        run_dir=run_dir,
        channel_name="ch",
        channel=ChannelConfig(channel_id="ch", voice_id="v"),
        urls=["https://youtube.com/shorts/test"],
        topic="테스트",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


class DummyStage(BaseStage):
    name = "dummy"
    stage_no = 1

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        return ctx


def test_base_stage_can_skip_false_initially(tmp_path):
    stage = DummyStage()
    ctx = make_ctx(tmp_path)
    assert stage.can_skip(ctx) is False


def test_base_stage_can_skip_true_when_in_completed(tmp_path):
    stage = DummyStage()
    ctx = make_ctx(tmp_path)
    ctx.completed_stages.append("dummy")
    assert stage.can_skip(ctx) is True


@pytest.mark.asyncio
async def test_base_stage_run_returns_ctx(tmp_path):
    stage = DummyStage()
    ctx = make_ctx(tmp_path)
    result = await stage.run(ctx)
    assert result is ctx
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/unit/test_pipeline_runner.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.stages.base'`

- [ ] **Step 3: BaseStage 구현**

`src/stages/base.py`:
```python
from abc import ABC, abstractmethod
from src.pipeline.context import PipelineContext


class BaseStage(ABC):
    name: str
    stage_no: int

    @abstractmethod
    async def run(self, ctx: PipelineContext) -> PipelineContext:
        """스테이지 실행. ctx를 받아 결과를 채워 반환."""
        ...

    def can_skip(self, ctx: PipelineContext) -> bool:
        """completed_stages에 이미 있으면 True."""
        return self.name in ctx.completed_stages
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/unit/test_pipeline_runner.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/stages/base.py tests/unit/test_pipeline_runner.py
git commit -m "feat: BaseStage 추상 클래스 + 테스트"
```

---

### Task 8: PipelineRunner — 실행 + 스킵 + 체크포인트

**Files:**
- Create: `src/pipeline/runner.py`
- Modify: `tests/unit/test_pipeline_runner.py`

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/unit/test_pipeline_runner.py` 하단에 추가:
```python
from src.pipeline.runner import PipelineRunner
from src.pipeline.state import CheckpointManager


class CountingStage(BaseStage):
    def __init__(self, name: str, no: int) -> None:
        self.name = name
        self.stage_no = no
        self.run_count = 0

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        self.run_count += 1
        return ctx


@pytest.mark.asyncio
async def test_runner_executes_all_stages(tmp_path):
    s1 = CountingStage("s1", 1)
    s2 = CountingStage("s2", 2)
    s3 = CountingStage("s3", 3)

    ctx = make_ctx(tmp_path)
    runner = PipelineRunner(stages=[s1, s2, s3], checkpoint=CheckpointManager())
    result = await runner.run(ctx)

    assert s1.run_count == 1
    assert s2.run_count == 1
    assert s3.run_count == 1
    assert result.status == "done"
    assert set(result.completed_stages) == {"s1", "s2", "s3"}


@pytest.mark.asyncio
async def test_runner_skips_completed_stages(tmp_path):
    s1 = CountingStage("s1", 1)
    s2 = CountingStage("s2", 2)

    ctx = make_ctx(tmp_path)
    ctx.completed_stages = ["s1"]  # s1 이미 완료

    runner = PipelineRunner(stages=[s1, s2], checkpoint=CheckpointManager())
    await runner.run(ctx)

    assert s1.run_count == 0  # 스킵됨
    assert s2.run_count == 1  # 실행됨


@pytest.mark.asyncio
async def test_runner_saves_checkpoint_after_each_stage(tmp_path):
    s1 = CountingStage("s1", 1)
    s2 = CountingStage("s2", 2)
    checkpoint = CheckpointManager()

    ctx = make_ctx(tmp_path)
    runner = PipelineRunner(stages=[s1, s2], checkpoint=checkpoint)
    await runner.run(ctx)

    saved = checkpoint.load(ctx.run_dir)
    assert "s1" in saved.completed_stages
    assert "s2" in saved.completed_stages
    assert saved.status == "done"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/unit/test_pipeline_runner.py::test_runner_executes_all_stages -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.pipeline.runner'`

- [ ] **Step 3: PipelineRunner 구현**

`src/pipeline/runner.py`:
```python
import asyncio
from loguru import logger
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext
from src.pipeline.state import CheckpointManager


class PipelineRunner:
    def __init__(
        self,
        stages: list[BaseStage],
        checkpoint: CheckpointManager,
        max_retries: int = 3,
    ) -> None:
        self.stages = stages
        self.checkpoint = checkpoint
        self.max_retries = max_retries

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        for stage in self.stages:
            if stage.can_skip(ctx):
                logger.info(f"⏩ [{stage.name}] 스킵")
                continue

            logger.info(f"▶ [{stage.name}] 시작")
            ctx.current_stage = stage.name
            ctx = await self._run_with_retry(stage, ctx)
            ctx.completed_stages.append(stage.name)
            self.checkpoint.save(ctx)
            logger.success(f"✅ [{stage.name}] 완료")

        ctx.status = "done"
        self.checkpoint.save(ctx)
        return ctx

    async def _run_with_retry(
        self, stage: BaseStage, ctx: PipelineContext
    ) -> PipelineContext:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                return await stage.run(ctx)
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(
                        f"[{stage.name}] 재시도 {attempt + 1}/{self.max_retries} "
                        f"({wait}s 후): {exc}"
                    )
                    await asyncio.sleep(wait)

        ctx.status = "failed"
        ctx.last_error = str(last_exc)
        self.checkpoint.save(ctx)
        raise last_exc  # type: ignore[misc]
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/unit/test_pipeline_runner.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/runner.py tests/unit/test_pipeline_runner.py
git commit -m "feat: PipelineRunner (실행/스킵/체크포인트) + 테스트"
```

---

### Task 9: PipelineRunner — 재시도 + 실패 처리

**Files:**
- Modify: `tests/unit/test_pipeline_runner.py`

- [ ] **Step 1: 재시도 테스트 추가**

`tests/unit/test_pipeline_runner.py` 하단에 추가:
```python
class FlakyStage(BaseStage):
    """처음 N번 실패, 그 이후 성공하는 테스트용 스테이지"""
    def __init__(self, fail_times: int) -> None:
        self.name = "flaky"
        self.stage_no = 1
        self.fail_times = fail_times
        self.attempt = 0

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        self.attempt += 1
        if self.attempt <= self.fail_times:
            raise RuntimeError(f"의도적 실패 {self.attempt}")
        return ctx


@pytest.mark.asyncio
async def test_runner_retries_on_failure(tmp_path, mocker):
    mocker.patch("src.pipeline.runner.asyncio.sleep")  # 대기시간 제거
    stage = FlakyStage(fail_times=2)  # 처음 2번 실패, 3번째 성공

    ctx = make_ctx(tmp_path)
    runner = PipelineRunner(
        stages=[stage],
        checkpoint=CheckpointManager(),
        max_retries=3,
    )
    result = await runner.run(ctx)

    assert stage.attempt == 3
    assert result.status == "done"


@pytest.mark.asyncio
async def test_runner_saves_failed_status_on_exhausted_retries(tmp_path, mocker):
    mocker.patch("src.pipeline.runner.asyncio.sleep")
    stage = FlakyStage(fail_times=99)  # 항상 실패

    ctx = make_ctx(tmp_path)
    checkpoint = CheckpointManager()
    runner = PipelineRunner(stages=[stage], checkpoint=checkpoint, max_retries=2)

    with pytest.raises(RuntimeError):
        await runner.run(ctx)

    saved = checkpoint.load(ctx.run_dir)
    assert saved.status == "failed"
    assert "의도적 실패" in saved.last_error
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/unit/test_pipeline_runner.py::test_runner_retries_on_failure -v
```

Expected: FAIL with `AttributeError` (FlakyStage 미정의)

- [ ] **Step 3: 테스트 통과 확인**

```bash
uv run pytest tests/unit/test_pipeline_runner.py -v
```

Expected: PASS (모든 테스트)

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_pipeline_runner.py
git commit -m "test: PipelineRunner 재시도 + 실패 처리 테스트"
```

---

### Task 10: 스텁 스테이지 8개

**Files:**
- Create: `src/stages/benchmark.py`, `script.py`, `tts.py`, `storyboard.py`, `image_video.py`, `edit.py`, `thumbnail.py`, `upload.py`

각 스텁은 Plan 2~5에서 실제 API 구현으로 교체됩니다.

- [ ] **Step 1: src/stages/benchmark.py**

```python
from loguru import logger
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext
from src.config.settings import Settings


class BenchmarkStage(BaseStage):
    name = "benchmark"
    stage_no = 1

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        logger.warning(f"[{self.name}] 스텁 — Plan 2에서 구현 예정")
        return ctx
```

- [ ] **Step 2: src/stages/script.py**

```python
from loguru import logger
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext
from src.config.settings import Settings


class ScriptStage(BaseStage):
    name = "script"
    stage_no = 2

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        logger.warning(f"[{self.name}] 스텁 — Plan 2에서 구현 예정")
        return ctx
```

- [ ] **Step 3: src/stages/tts.py**

```python
from loguru import logger
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext
from src.config.settings import Settings


class TTSStage(BaseStage):
    name = "tts"
    stage_no = 3

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        logger.warning(f"[{self.name}] 스텁 — Plan 3에서 구현 예정")
        return ctx
```

- [ ] **Step 4: src/stages/storyboard.py**

```python
from loguru import logger
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext
from src.config.settings import Settings


class StoryboardStage(BaseStage):
    name = "storyboard"
    stage_no = 4

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        logger.warning(f"[{self.name}] 스텁 — Plan 3에서 구현 예정")
        return ctx
```

- [ ] **Step 5: src/stages/image_video.py**

```python
from loguru import logger
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext
from src.config.settings import Settings


class ImageVideoStage(BaseStage):
    name = "image_video"
    stage_no = 5

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        logger.warning(f"[{self.name}] 스텁 — Plan 4에서 구현 예정")
        return ctx
```

- [ ] **Step 6: src/stages/edit.py**

```python
from loguru import logger
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext
from src.config.settings import Settings


class EditStage(BaseStage):
    name = "edit"
    stage_no = 6

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        logger.warning(f"[{self.name}] 스텁 — Plan 4에서 구현 예정")
        return ctx
```

- [ ] **Step 7: src/stages/thumbnail.py**

```python
from loguru import logger
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext
from src.config.settings import Settings


class ThumbnailStage(BaseStage):
    name = "thumbnail"
    stage_no = 7

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        logger.warning(f"[{self.name}] 스텁 — Plan 5에서 구현 예정")
        return ctx
```

- [ ] **Step 8: src/stages/upload.py**

```python
from loguru import logger
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext
from src.config.settings import Settings


class UploadStage(BaseStage):
    name = "upload"
    stage_no = 8

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        logger.warning(f"[{self.name}] 스텁 — Plan 5에서 구현 예정")
        return ctx
```

- [ ] **Step 9: Commit**

```bash
git add src/stages/
git commit -m "feat: 스텁 스테이지 8개 (benchmark~upload)"
```

---

### Task 11: CLI + run.py

**Files:**
- Create: `src/cli/main.py`
- Create: `run.py`
- Create: `tests/unit/test_cli.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/unit/test_cli.py`:
```python
import pytest
from src.cli.main import parse_args


def test_parse_new_run_args():
    args = parse_args([
        "--urls", "https://youtube.com/shorts/abc", "https://youtube.com/shorts/xyz",
        "--topic", "카페인 과다복용 부작용 5가지",
        "--channel", "channel_a",
        "--duration", "60",
    ])
    assert args.urls == ["https://youtube.com/shorts/abc", "https://youtube.com/shorts/xyz"]
    assert args.topic == "카페인 과다복용 부작용 5가지"
    assert args.channel == "channel_a"
    assert args.duration == 60
    assert args.style is None
    assert args.resume is None


def test_parse_resume_args():
    args = parse_args(["--resume", "runs/channel_a/20260416_143022_abc123"])
    assert args.resume == "runs/channel_a/20260416_143022_abc123"
    assert args.urls is None


def test_parse_requires_topic_with_urls():
    with pytest.raises(SystemExit):
        parse_args(["--urls", "https://youtube.com/shorts/abc"])


def test_parse_urls_and_resume_mutually_exclusive():
    with pytest.raises(SystemExit):
        parse_args([
            "--urls", "https://youtube.com/shorts/abc",
            "--resume", "runs/channel_a/run1",
            "--topic", "test",
        ])
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/unit/test_cli.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.cli.main'`

- [ ] **Step 3: src/cli/main.py 구현**

```python
import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="YouTube Shorts 자동화 파이프라인")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--urls", nargs="+", metavar="URL",
        help="래퍼런스 YouTube URL (1~3개)",
    )
    group.add_argument(
        "--resume", metavar="RUN_DIR",
        help="실패한 파이프라인 재시작 (예: runs/channel_a/20260416_143022_abc123)",
    )
    parser.add_argument("--topic", help="영상 소재 (--urls 사용 시 필수)")
    parser.add_argument("--channel", default="channel_a", help="채널 이름 (기본: channel_a)")
    parser.add_argument("--style", help="비주얼 스타일 (선택)")
    parser.add_argument("--duration", type=int, default=60, help="목표 길이 초 (기본: 60)")
    parser.add_argument(
        "--from-stage", dest="from_stage",
        help="특정 스테이지부터 강제 재실행 (--resume과 함께 사용)",
    )
    return parser


def parse_args(args=None):
    parser = build_parser()
    parsed = parser.parse_args(args)
    if parsed.urls and not parsed.topic:
        parser.error("--urls 사용 시 --topic 필수")
    return parsed
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/unit/test_cli.py -v
```

Expected: PASS

- [ ] **Step 5: run.py 작성**

```python
import asyncio
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from src.cli.main import parse_args
from src.config.channel import load_channel_config
from src.config.settings import Settings
from src.pipeline.context import PipelineContext
from src.pipeline.runner import PipelineRunner
from src.pipeline.state import CheckpointManager
from src.stages.base import BaseStage
from src.stages.benchmark import BenchmarkStage
from src.stages.edit import EditStage
from src.stages.image_video import ImageVideoStage
from src.stages.script import ScriptStage
from src.stages.storyboard import StoryboardStage
from src.stages.thumbnail import ThumbnailStage
from src.stages.tts import TTSStage
from src.stages.upload import UploadStage


def _make_run_id() -> str:
    now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{now}_{secrets.token_hex(3)}"


def _build_stages(settings: Settings) -> list[BaseStage]:
    return [
        BenchmarkStage(settings=settings),
        ScriptStage(settings=settings),
        TTSStage(settings=settings),
        StoryboardStage(settings=settings),
        ImageVideoStage(settings=settings),
        EditStage(settings=settings),
        ThumbnailStage(settings=settings),
        UploadStage(settings=settings),
    ]


async def main() -> None:
    args = parse_args()
    settings = Settings()
    checkpoint = CheckpointManager()

    if args.resume:
        run_dir = Path(args.resume)
        ctx = checkpoint.load(run_dir)
        logger.info(f"▶ 재시작: {ctx.run_id} | 완료: {ctx.completed_stages}")

        if args.from_stage:
            stage_names = [s.name for s in _build_stages(settings)]
            if args.from_stage not in stage_names:
                logger.error(f"알 수 없는 스테이지: {args.from_stage}")
                sys.exit(1)
            idx = stage_names.index(args.from_stage)
            ctx.completed_stages = [
                s for s in ctx.completed_stages if s not in stage_names[idx:]
            ]
            logger.info(f"강제 재실행: {args.from_stage}부터")
    else:
        channel = load_channel_config(args.channel)
        run_id = _make_run_id()
        run_dir = Path("runs") / args.channel / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc).isoformat()
        ctx = PipelineContext(
            run_id=run_id,
            run_dir=run_dir,
            channel_name=args.channel,
            channel=channel,
            urls=args.urls,
            topic=args.topic,
            style=args.style,
            duration=args.duration,
            created_at=now,
            updated_at=now,
        )
        checkpoint.save(ctx)
        logger.info(f"▶ 신규 실행: {run_id}")

    stages = _build_stages(settings)
    runner = PipelineRunner(
        stages=stages,
        checkpoint=checkpoint,
        max_retries=settings.max_retries,
    )

    try:
        ctx = await runner.run(ctx)
        logger.success(f"🎉 완료! 결과: {ctx.run_dir}")
    except Exception as e:
        logger.error(f"파이프라인 실패: {e}")
        logger.info(f"재시작: uv run python run.py --resume {ctx.run_dir}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 6: Commit**

```bash
git add src/cli/main.py run.py tests/unit/test_cli.py
git commit -m "feat: CLI (argparse) + run.py 진입점"
```

---

### Task 12: 재시작 통합 테스트

**Files:**
- Create: `tests/integration/test_resume.py`

- [ ] **Step 1: 통합 테스트 작성**

`tests/integration/test_resume.py`:
```python
import pytest
from pathlib import Path
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext
from src.pipeline.runner import PipelineRunner
from src.pipeline.state import CheckpointManager
from src.config.channel import ChannelConfig


def make_ctx(tmp_path: Path) -> PipelineContext:
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    return PipelineContext(
        run_id="run1",
        run_dir=run_dir,
        channel_name="ch",
        channel=ChannelConfig(channel_id="ch", voice_id="v"),
        urls=["https://youtube.com/shorts/test"],
        topic="테스트",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


class TrackingStage(BaseStage):
    def __init__(self, name: str, no: int) -> None:
        self.name = name
        self.stage_no = no
        self.ran = False

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        self.ran = True
        return ctx


@pytest.mark.asyncio
async def test_resume_skips_completed_runs_remaining(tmp_path):
    """s1, s2 완료 상태로 저장 → resume 시 s3만 실행"""
    s1 = TrackingStage("s1", 1)
    s2 = TrackingStage("s2", 2)
    s3 = TrackingStage("s3", 3)
    checkpoint = CheckpointManager()

    ctx = make_ctx(tmp_path)
    ctx.completed_stages = ["s1", "s2"]
    checkpoint.save(ctx)

    restored = checkpoint.load(ctx.run_dir)
    runner = PipelineRunner(stages=[s1, s2, s3], checkpoint=checkpoint)
    result = await runner.run(restored)

    assert s1.ran is False   # 스킵
    assert s2.ran is False   # 스킵
    assert s3.ran is True    # 실행됨
    assert result.status == "done"


@pytest.mark.asyncio
async def test_new_runner_instance_honours_checkpoint(tmp_path):
    """새 PipelineRunner 인스턴스로 재시작해도 체크포인트 반영"""
    checkpoint = CheckpointManager()
    ctx = make_ctx(tmp_path)

    # 첫 실행: s1만
    s1 = TrackingStage("s1", 1)
    runner1 = PipelineRunner(stages=[s1], checkpoint=checkpoint)
    await runner1.run(ctx)

    # 두 번째 실행: 새 인스턴스, s1 + s2
    restored = checkpoint.load(ctx.run_dir)
    s1_new = TrackingStage("s1", 1)
    s2_new = TrackingStage("s2", 2)
    runner2 = PipelineRunner(stages=[s1_new, s2_new], checkpoint=checkpoint)
    await runner2.run(restored)

    assert s1_new.ran is False   # s1 이미 완료 → 스킵
    assert s2_new.ran is True    # s2 실행됨
```

- [ ] **Step 2: 테스트 실행**

```bash
uv run pytest tests/integration/test_resume.py -v
```

Expected: PASS

- [ ] **Step 3: 전체 테스트 통과 확인**

```bash
uv run pytest -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_resume.py
git commit -m "test: 재시작 통합 테스트 (체크포인트 → resume 시나리오)"
```

---

### Task 13: Docker 스켈레톤

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`

- [ ] **Step 1: Dockerfile 작성**

```dockerfile
FROM python:3.12-slim

RUN pip install uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

COPY src/ src/
COPY channels/ channels/
COPY run.py .

VOLUME ["/app/runs", "/app/cache", "/app/secrets"]

ENTRYPOINT ["uv", "run", "python", "run.py"]
```

- [ ] **Step 2: docker-compose.yml 작성**

```yaml
services:
  pipeline:
    build: .
    env_file: .env
    volumes:
      - ./runs:/app/runs
      - ./cache:/app/cache
      - ./secrets:/app/secrets
      - ./channels:/app/channels
    command: >
      --urls "https://youtube.com/shorts/example"
      --topic "테스트 주제"
      --channel channel_a
```

- [ ] **Step 3: Commit**

```bash
git add Dockerfile docker-compose.yml
git commit -m "chore: Docker 스켈레톤 (Dockerfile + docker-compose.yml)"
```

---

### Task 14: 최종 확인 + Push

- [ ] **Step 1: 전체 테스트 최종 통과 확인**

```bash
uv run pytest -v
```

Expected: 모든 테스트 PASS (FAILED 0개)

- [ ] **Step 2: Push**

```bash
git push origin master
```
