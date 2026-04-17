# Plan 4: ImageVideoStage + EditStage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** fal.ai(Flux + Kling)로 씬별 이미지-영상을 생성하고 FFmpeg으로 최종 Shorts 영상을 편집한다.

**Architecture:** FalService가 fal.ai API로 Flux 이미지 생성과 Kling 이미지-영상 변환을 담당하고, FFmpegService가 비동기 서브프로세스로 FFmpeg을 실행한다. ImageVideoStage는 씬별 병렬 처리(Semaphore N=3)에 체크포인트를 구현하고, EditStage는 씬별 합성-concat-자막 burn-in 순으로 최종 영상을 생성한다.

**Tech Stack:** fal-client, httpx, asyncio.Semaphore, asyncio subprocess

---

## 사전 작업: worktree 생성 (repo root에서 실행)

```bash
git worktree add .worktrees/plan4-image-video-edit -b feat/plan4-image-video-edit feat/plan3-tts-storyboard
cd .worktrees/plan4-image-video-edit
```

---

## File Map

| 파일 | 작업 | 역할 |
|------|------|------|
| `pyproject.toml` | Modify | fal-client 의존성 추가 |
| `src/config/settings.py` | Modify | `flux_api_key`/`kling_api_key` → `fal_api_key` |
| `src/services/fal.py` | Create | fal.ai Flux+Kling 클라이언트 |
| `src/services/ffmpeg.py` | Create | FFmpeg 비동기 서브프로세스 래퍼 |
| `src/stages/image_video.py` | Modify | 스텁 → 실제 구현 |
| `src/stages/edit.py` | Modify | 스텁 → 실제 구현 |
| `tests/unit/test_fal_service.py` | Create | FalService 단위 테스트 |
| `tests/unit/test_ffmpeg_service.py` | Create | FFmpegService 단위 테스트 |
| `tests/unit/test_image_video_stage.py` | Create | ImageVideoStage 단위 테스트 |
| `tests/unit/test_edit_stage.py` | Create | EditStage 단위 테스트 |

---

## Task 1: Settings + pyproject.toml 업데이트

**Files:** `src/config/settings.py`, `pyproject.toml`, `tests/unit/test_*.py`

- [ ] **Step 1: settings.py 수정** — `flux_api_key`/`kling_api_key` 제거, `fal_api_key` 추가

```python
# src/config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    anthropic_api_key: str
    elevenlabs_api_key: str
    youtube_api_key: str
    fal_api_key: str
    youtube_client_secret_path: str = "secrets/youtube_client_secret.json"
    max_retries: int = 3
    retry_backoff_base: int = 2
    default_concurrency: int = 3
    default_duration: int = 60
    log_level: str = "INFO"
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
```

- [ ] **Step 2: pyproject.toml에 fal-client 추가**

기존 `dependencies` 리스트에 `"fal-client>=0.10.0",` 추가.

- [ ] **Step 3: 기존 테스트 make_settings() 수정**

`test_tts_stage.py`, `test_storyboard_stage.py`, `test_benchmark_stage.py`, `test_script_stage.py`에서 `flux_api_key="flux-test"`, `kling_api_key="kling-test"` 제거하고 `fal_api_key="fal-test"` 추가. `test_config.py`에서도 동일하게 수정.

- [ ] **Step 4: 기존 테스트 전체 통과 확인**

```bash
uv run pytest tests/ -v
```
Expected: 기존 테스트 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add pyproject.toml src/config/settings.py tests/unit/
git commit -m "chore: fal_api_key 통합 (flux_api_key+kling_api_key 제거)"
```

---

## Task 2: FalService 구현

**Files:** `src/services/fal.py`, `tests/unit/test_fal_service.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/unit/test_fal_service.py
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_generate_image_saves_png(tmp_path):
    from src.services.fal import FalService
    service = FalService(api_key="fal-test")
    with patch("src.services.fal.fal_client") as mock_fal, \
         patch("src.services.fal.httpx.AsyncClient") as mock_http:
        mock_fal.run_async = AsyncMock(return_value={"images": [{"url": "https://cdn.fal.ai/img.png"}]})
        mock_resp = MagicMock()
        mock_resp.content = b"PNG"
        mock_resp.raise_for_status = MagicMock()
        mock_http.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(get=AsyncMock(return_value=mock_resp)))
        result = await service.generate_image(
            scene_no=1, enhanced_prompt="dark", negative_prompt="blur", run_dir=tmp_path)
    assert result == str(tmp_path / "image_video" / "scene_1.png")
    assert (tmp_path / "image_video" / "scene_1.png").exists()


@pytest.mark.asyncio
async def test_generate_video_saves_mp4(tmp_path):
    from src.services.fal import FalService
    service = FalService(api_key="fal-test")
    image_path = tmp_path / "image_video" / "scene_1.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"img")
    with patch("src.services.fal.fal_client") as mock_fal, \
         patch("src.services.fal.httpx.AsyncClient") as mock_http:
        mock_fal.upload_file_async = AsyncMock(return_value="https://cdn.fal.ai/up.png")
        mock_fal.subscribe_async = AsyncMock(return_value={"video": {"url": "https://cdn.fal.ai/vid.mp4"}})
        mock_resp = MagicMock()
        mock_resp.content = b"MP4"
        mock_resp.raise_for_status = MagicMock()
        mock_http.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(get=AsyncMock(return_value=mock_resp)))
        result = await service.generate_video(
            scene_no=1, image_path=str(image_path), prompt="dark", run_dir=tmp_path)
    assert result == str(tmp_path / "image_video" / "scene_1.mp4")
    assert (tmp_path / "image_video" / "scene_1.mp4").exists()


@pytest.mark.asyncio
async def test_generate_image_skips_if_exists(tmp_path):
    from src.services.fal import FalService
    service = FalService(api_key="fal-test")
    p = tmp_path / "image_video" / "scene_1.png"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"x")
    with patch("src.services.fal.fal_client") as mock_fal:
        result = await service.generate_image(
            scene_no=1, enhanced_prompt="p", negative_prompt="n", run_dir=tmp_path)
        mock_fal.run_async.assert_not_called()
    assert result == str(p)


@pytest.mark.asyncio
async def test_generate_video_skips_if_exists(tmp_path):
    from src.services.fal import FalService
    service = FalService(api_key="fal-test")
    p = tmp_path / "image_video" / "scene_1.mp4"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"x")
    with patch("src.services.fal.fal_client") as mock_fal:
        result = await service.generate_video(
            scene_no=1, image_path="unused", prompt="p", run_dir=tmp_path)
        mock_fal.subscribe_async.assert_not_called()
    assert result == str(p)
```

- [ ] **Step 2: 테스트 실패 확인** — `uv run pytest tests/unit/test_fal_service.py -v` → FAIL

- [ ] **Step 3: FalService 구현**

```python
# src/services/fal.py
import fal_client
import httpx
from pathlib import Path
from loguru import logger


class FalService:
    def __init__(self, api_key: str) -> None:
        fal_client.api_key = api_key

    async def generate_image(
        self, scene_no: int, enhanced_prompt: str, negative_prompt: str, run_dir: Path,
    ) -> str:
        out_dir = run_dir / "image_video"
        out_dir.mkdir(parents=True, exist_ok=True)
        image_path = out_dir / f"scene_{scene_no}.png"
        if image_path.exists():
            logger.debug(f"[fal] 씬 {scene_no} 이미지 스킵")
            return str(image_path)
        logger.info(f"[fal] 씬 {scene_no} Flux 이미지 생성 중")
        result = await fal_client.run_async(
            "fal-ai/flux/schnell",
            arguments={
                "prompt": enhanced_prompt,
                "negative_prompt": negative_prompt,
                "image_size": "portrait_4_3",
                "num_inference_steps": 4,
                "num_images": 1,
            },
        )
        image_url: str = result["images"][0]["url"]
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(image_url)
            resp.raise_for_status()
            image_path.write_bytes(resp.content)
        logger.debug(f"[fal] 씬 {scene_no} 이미지 저장: {image_path}")
        return str(image_path)

    async def generate_video(
        self, scene_no: int, image_path: str, prompt: str, run_dir: Path,
    ) -> str:
        out_dir = run_dir / "image_video"
        out_dir.mkdir(parents=True, exist_ok=True)
        video_path = out_dir / f"scene_{scene_no}.mp4"
        if video_path.exists():
            logger.debug(f"[fal] 씬 {scene_no} 영상 스킵")
            return str(video_path)
        logger.info(f"[fal] 씬 {scene_no} Kling 영상 생성 중")
        uploaded_url: str = await fal_client.upload_file_async(image_path)
        result = await fal_client.subscribe_async(
            "fal-ai/kling-video/v1/standard/image-to-video",
            arguments={
                "image_url": uploaded_url,
                "prompt": prompt,
                "duration": "5",
                "aspect_ratio": "9:16",
            },
        )
        video_url: str = result["video"]["url"]
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.get(video_url)
            resp.raise_for_status()
            video_path.write_bytes(resp.content)
        logger.debug(f"[fal] 씬 {scene_no} 영상 저장: {video_path}")
        return str(video_path)
```

- [ ] **Step 4: 테스트 통과 확인** — `uv run pytest tests/unit/test_fal_service.py -v` → 4 PASS

- [ ] **Step 5: 커밋**

```bash
git add src/services/fal.py tests/unit/test_fal_service.py
git commit -m "feat: FalService — fal.ai Flux 이미지 + Kling 영상 생성"
```

---

## Task 3: FFmpegService 구현

**Files:** `src/services/ffmpeg.py`, `tests/unit/test_ffmpeg_service.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/unit/test_ffmpeg_service.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_merge_calls_ffmpeg():
    from src.services.ffmpeg import FFmpegService
    service = FFmpegService()
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))
    mock_proc.returncode = 0
    with patch("src.services.ffmpeg.asyncio.create_subprocess_exec",
               AsyncMock(return_value=mock_proc)) as sp:
        await service.merge_video_audio(
            video_path="/v.mp4", audio_path="/a.mp3", output_path="/o.mp4")
    args = sp.call_args[0]
    assert "ffmpeg" in args[0] and "/v.mp4" in args and "/a.mp3" in args and "/o.mp4" in args


@pytest.mark.asyncio
async def test_concat_uses_concat_demuxer():
    from src.services.ffmpeg import FFmpegService
    service = FFmpegService()
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))
    mock_proc.returncode = 0
    with patch("src.services.ffmpeg.asyncio.create_subprocess_exec",
               AsyncMock(return_value=mock_proc)) as sp, \
         patch("builtins.open", MagicMock()):
        await service.concat_videos(
            video_paths=["/a.mp4", "/b.mp4"], output_path="/o.mp4")
    args = sp.call_args[0]
    assert "-f" in args and args[list(args).index("-f") + 1] == "concat"


@pytest.mark.asyncio
async def test_burn_subtitles_uses_subtitles_filter():
    from src.services.ffmpeg import FFmpegService
    service = FFmpegService()
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))
    mock_proc.returncode = 0
    with patch("src.services.ffmpeg.asyncio.create_subprocess_exec",
               AsyncMock(return_value=mock_proc)) as sp:
        await service.burn_subtitles(
            video_path="/v.mp4", srt_path="/s.srt", output_path="/o.mp4")
    args = sp.call_args[0]
    assert any("subtitles" in str(a) for a in args)


@pytest.mark.asyncio
async def test_ffmpeg_raises_on_failure():
    from src.services.ffmpeg import FFmpegService
    service = FFmpegService()
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b"", b"err"))
    mock_proc.returncode = 1
    with patch("src.services.ffmpeg.asyncio.create_subprocess_exec",
               AsyncMock(return_value=mock_proc)):
        with pytest.raises(RuntimeError, match="FFmpeg"):
            await service.merge_video_audio(
                video_path="/a.mp4", audio_path="/b.mp3", output_path="/o.mp4")
```

- [ ] **Step 2: 테스트 실패 확인** — `uv run pytest tests/unit/test_ffmpeg_service.py -v` → FAIL

- [ ] **Step 3: FFmpegService 구현**

```python
# src/services/ffmpeg.py
import asyncio
from pathlib import Path
from loguru import logger


class FFmpegService:
    async def _run(self, *args: str) -> None:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg 실행 실패 (code={proc.returncode}): {stderr.decode()}")

    async def merge_video_audio(
        self, video_path: str, audio_path: str, output_path: str,
    ) -> None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"[ffmpeg] merge: {video_path} + {audio_path}")
        await self._run(
            "ffmpeg", "-y",
            "-i", video_path, "-i", audio_path,
            "-c:v", "copy", "-c:a", "aac", "-shortest",
            output_path,
        )

    async def concat_videos(
        self, video_paths: list[str], output_path: str,
    ) -> None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        list_path = str(Path(output_path).parent / "concat_list.txt")
        with open(list_path, "w", encoding="utf-8") as f:
            f.write("\n".join(f"file '{p}'" for p in video_paths))
        logger.debug(f"[ffmpeg] concat {len(video_paths)}개 => {output_path}")
        await self._run(
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_path, "-c", "copy",
            output_path,
        )

    async def burn_subtitles(
        self, video_path: str, srt_path: str, output_path: str,
    ) -> None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")
        logger.debug(f"[ffmpeg] burn_subtitles: {srt_path}")
        await self._run(
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"subtitles={srt_escaped}",
            "-c:a", "copy",
            output_path,
        )
```

- [ ] **Step 4: 테스트 통과 확인** — `uv run pytest tests/unit/test_ffmpeg_service.py -v` → 4 PASS

- [ ] **Step 5: 커밋**

```bash
git add src/services/ffmpeg.py tests/unit/test_ffmpeg_service.py
git commit -m "feat: FFmpegService — merge/concat/subtitle burn-in"
```

---

## Task 4: ImageVideoStage 구현

**Files:** `src/stages/image_video.py`, `tests/unit/test_image_video_stage.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/unit/test_image_video_stage.py
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from src.config.channel import ChannelConfig
from src.config.settings import Settings
from src.pipeline.context import (
    PipelineContext, StoryboardResult, EnhancedScene, ImageVideoResult, SceneMedia,
)


def make_settings():
    return Settings(
        anthropic_api_key="sk-test", elevenlabs_api_key="el-test",
        fal_api_key="fal-test", youtube_api_key="yt-test",
    )


def make_ctx(tmp_path: Path) -> PipelineContext:
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    ctx = PipelineContext(
        run_id="run1", run_dir=run_dir, channel_name="ch",
        channel=ChannelConfig(channel_id="ch", voice_id="v",
                              visual_style_presets={"default": "dark"}),
        urls=["https://youtube.com/watch?v=abc"], topic="test",
        created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
    )
    ctx.storyboard = StoryboardResult(
        scenes=[
            EnhancedScene(scene_no=1, enhanced_prompt="shot 1", negative_prompt="blur"),
            EnhancedScene(scene_no=2, enhanced_prompt="shot 2", negative_prompt="blur"),
        ],
        visual_style="dark",
    )
    return ctx


@pytest.mark.asyncio
async def test_sets_ctx_image_video(tmp_path):
    from src.stages.image_video import ImageVideoStage
    stage = ImageVideoStage(settings=make_settings())
    ctx = make_ctx(tmp_path)
    with patch("src.stages.image_video.FalService") as MockFal:
        mock_fal = MockFal.return_value
        mock_fal.generate_image = AsyncMock(side_effect=[
            str(ctx.run_dir / "image_video/scene_1.png"),
            str(ctx.run_dir / "image_video/scene_2.png"),
        ])
        mock_fal.generate_video = AsyncMock(side_effect=[
            str(ctx.run_dir / "image_video/scene_1.mp4"),
            str(ctx.run_dir / "image_video/scene_2.mp4"),
        ])
        result = await stage.run(ctx)
    assert result.image_video is not None
    assert len(result.image_video.scenes) == 2
    assert result.image_video.scenes[0].scene_no == 1


@pytest.mark.asyncio
async def test_passes_prompts_to_fal(tmp_path):
    from src.stages.image_video import ImageVideoStage
    stage = ImageVideoStage(settings=make_settings())
    ctx = make_ctx(tmp_path)
    with patch("src.stages.image_video.FalService") as MockFal:
        mock_fal = MockFal.return_value
        mock_fal.generate_image = AsyncMock(side_effect=[
            str(ctx.run_dir / "image_video/scene_1.png"),
            str(ctx.run_dir / "image_video/scene_2.png"),
        ])
        mock_fal.generate_video = AsyncMock(side_effect=[
            str(ctx.run_dir / "image_video/scene_1.mp4"),
            str(ctx.run_dir / "image_video/scene_2.mp4"),
        ])
        await stage.run(ctx)
    calls = {c[1]["scene_no"]: c[1] for c in mock_fal.generate_image.call_args_list}
    assert calls[1]["enhanced_prompt"] == "shot 1"
    assert calls[2]["enhanced_prompt"] == "shot 2"


@pytest.mark.asyncio
async def test_raises_if_no_storyboard(tmp_path):
    from src.stages.image_video import ImageVideoStage
    stage = ImageVideoStage(settings=make_settings())
    ctx = make_ctx(tmp_path)
    ctx.storyboard = None
    with pytest.raises(ValueError, match="storyboard"):
        await stage.run(ctx)
```

- [ ] **Step 2: 테스트 실패 확인** — `uv run pytest tests/unit/test_image_video_stage.py -v` → FAIL

- [ ] **Step 3: ImageVideoStage 구현**

```python
# src/stages/image_video.py
import asyncio
from loguru import logger
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext, ImageVideoResult, SceneMedia
from src.config.settings import Settings
from src.services.fal import FalService


class ImageVideoStage(BaseStage):
    name = "image_video"
    stage_no = 5

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.storyboard is None:
            raise ValueError("storyboard 결과가 없습니다. StoryboardStage를 먼저 실행하세요.")

        fal = FalService(api_key=self.settings.fal_api_key)
        semaphore = asyncio.Semaphore(self.settings.default_concurrency)

        async def process_scene(s) -> SceneMedia:
            async with semaphore:
                image_path = await fal.generate_image(
                    scene_no=s.scene_no,
                    enhanced_prompt=s.enhanced_prompt,
                    negative_prompt=s.negative_prompt,
                    run_dir=ctx.run_dir,
                )
                video_path = await fal.generate_video(
                    scene_no=s.scene_no,
                    image_path=image_path,
                    prompt=s.enhanced_prompt,
                    run_dir=ctx.run_dir,
                )
                logger.debug(f"[image_video] 씬 {s.scene_no} 완료")
                return SceneMedia(scene_no=s.scene_no, image_path=image_path, video_path=video_path)

        logger.info(f"[image_video] {len(ctx.storyboard.scenes)}개 씬 처리 시작")
        scenes = await asyncio.gather(*[process_scene(s) for s in ctx.storyboard.scenes])
        ctx.image_video = ImageVideoResult(scenes=sorted(scenes, key=lambda s: s.scene_no))
        logger.success(f"[image_video] 완료: {len(scenes)}개 씬")
        return ctx
```

- [ ] **Step 4: 테스트 통과 확인** — `uv run pytest tests/unit/test_image_video_stage.py -v` → 3 PASS

- [ ] **Step 5: 커밋**

```bash
git add src/stages/image_video.py tests/unit/test_image_video_stage.py
git commit -m "feat: ImageVideoStage — fal.ai Flux+Kling 병렬 처리"
```

---

## Task 5: EditStage 구현

**Files:** `src/stages/edit.py`, `tests/unit/test_edit_stage.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/unit/test_edit_stage.py
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from src.config.channel import ChannelConfig
from src.config.settings import Settings
from src.pipeline.context import (
    PipelineContext, TTSResult, SceneTTS,
    ImageVideoResult, SceneMedia, EditResult,
)


def make_settings():
    return Settings(
        anthropic_api_key="sk-test", elevenlabs_api_key="el-test",
        fal_api_key="fal-test", youtube_api_key="yt-test",
    )


def make_ctx(tmp_path: Path) -> PipelineContext:
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    ctx = PipelineContext(
        run_id="run1", run_dir=run_dir, channel_name="ch",
        channel=ChannelConfig(channel_id="ch", voice_id="v",
                              visual_style_presets={"default": "dark"}),
        urls=["https://youtube.com/watch?v=abc"], topic="test",
        created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
    )
    ctx.tts = TTSResult(
        scenes=[
            SceneTTS(scene_no=1, audio_path="tts/scene_1.mp3", srt_path="tts/scene_1.srt"),
            SceneTTS(scene_no=2, audio_path="tts/scene_2.mp3", srt_path="tts/scene_2.srt"),
        ],
        voice_id="v",
    )
    ctx.image_video = ImageVideoResult(
        scenes=[
            SceneMedia(scene_no=1, image_path="image_video/scene_1.png",
                       video_path="image_video/scene_1.mp4"),
            SceneMedia(scene_no=2, image_path="image_video/scene_2.png",
                       video_path="image_video/scene_2.mp4"),
        ]
    )
    return ctx


@pytest.mark.asyncio
async def test_sets_ctx_edit(tmp_path):
    from src.stages.edit import EditStage
    stage = EditStage(settings=make_settings())
    ctx = make_ctx(tmp_path)
    with patch("src.stages.edit.FFmpegService") as MockFF:
        mock_ff = MockFF.return_value
        mock_ff.merge_video_audio = AsyncMock()
        mock_ff.concat_videos = AsyncMock()
        mock_ff.burn_subtitles = AsyncMock()
        result = await stage.run(ctx)
    assert result.edit is not None
    assert isinstance(result.edit, EditResult)
    assert result.edit.video_path == "final_shorts.mp4"


@pytest.mark.asyncio
async def test_calls_merge_per_scene(tmp_path):
    from src.stages.edit import EditStage
    stage = EditStage(settings=make_settings())
    ctx = make_ctx(tmp_path)
    with patch("src.stages.edit.FFmpegService") as MockFF:
        mock_ff = MockFF.return_value
        mock_ff.merge_video_audio = AsyncMock()
        mock_ff.concat_videos = AsyncMock()
        mock_ff.burn_subtitles = AsyncMock()
        await stage.run(ctx)
    assert mock_ff.merge_video_audio.call_count == 2


@pytest.mark.asyncio
async def test_concat_before_burn(tmp_path):
    from src.stages.edit import EditStage
    stage = EditStage(settings=make_settings())
    ctx = make_ctx(tmp_path)
    call_order = []
    with patch("src.stages.edit.FFmpegService") as MockFF:
        mock_ff = MockFF.return_value
        mock_ff.merge_video_audio = AsyncMock()
        mock_ff.concat_videos = AsyncMock(
            side_effect=lambda **kw: call_order.append("concat") or None)
        mock_ff.burn_subtitles = AsyncMock(
            side_effect=lambda **kw: call_order.append("burn") or None)
        await stage.run(ctx)
    assert call_order == ["concat", "burn"]


@pytest.mark.asyncio
async def test_raises_if_no_tts(tmp_path):
    from src.stages.edit import EditStage
    stage = EditStage(settings=make_settings())
    ctx = make_ctx(tmp_path)
    ctx.tts = None
    with pytest.raises(ValueError, match="tts"):
        await stage.run(ctx)


@pytest.mark.asyncio
async def test_raises_if_no_image_video(tmp_path):
    from src.stages.edit import EditStage
    stage = EditStage(settings=make_settings())
    ctx = make_ctx(tmp_path)
    ctx.image_video = None
    with pytest.raises(ValueError, match="image_video"):
        await stage.run(ctx)
```

- [ ] **Step 2: 테스트 실패 확인** — `uv run pytest tests/unit/test_edit_stage.py -v` → FAIL

- [ ] **Step 3: EditStage 구현**

```python
# src/stages/edit.py
from pathlib import Path
from loguru import logger
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext, EditResult
from src.config.settings import Settings
from src.services.ffmpeg import FFmpegService


class EditStage(BaseStage):
    name = "edit"
    stage_no = 6

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.tts is None:
            raise ValueError("tts 결과가 없습니다. TTSStage를 먼저 실행하세요.")
        if ctx.image_video is None:
            raise ValueError("image_video 결과가 없습니다. ImageVideoStage를 먼저 실행하세요.")

        ffmpeg = FFmpegService()
        edit_dir = ctx.run_dir / "edit"
        edit_dir.mkdir(parents=True, exist_ok=True)

        tts_by_scene = {s.scene_no: s for s in ctx.tts.scenes}
        iv_by_scene = {s.scene_no: s for s in ctx.image_video.scenes}
        scene_nos = sorted(tts_by_scene.keys())

        logger.info(f"[edit] {len(scene_nos)}개 씬 합성 시작")
        merged_paths: list[str] = []
        for n in scene_nos:
            merged = str(edit_dir / f"scene_{n}_merged.mp4")
            await ffmpeg.merge_video_audio(
                video_path=str(ctx.run_dir / iv_by_scene[n].video_path),
                audio_path=str(ctx.run_dir / tts_by_scene[n].audio_path),
                output_path=merged,
            )
            merged_paths.append(merged)
            logger.debug(f"[edit] 씬 {n} 합성 완료")

        concat_path = str(edit_dir / "concat.mp4")
        await ffmpeg.concat_videos(video_paths=merged_paths, output_path=concat_path)

        first_srt = str(ctx.run_dir / ctx.tts.scenes[0].srt_path)
        final_path = str(ctx.run_dir / "final_shorts.mp4")
        await ffmpeg.burn_subtitles(
            video_path=concat_path, srt_path=first_srt, output_path=final_path,
        )
        logger.success("[edit] 최종 영상 생성 완료")
        ctx.edit = EditResult(video_path="final_shorts.mp4")
        return ctx
```

- [ ] **Step 4: 테스트 통과 확인** — `uv run pytest tests/unit/test_edit_stage.py -v` → 5 PASS

- [ ] **Step 5: 커밋**

```bash
git add src/stages/edit.py tests/unit/test_edit_stage.py
git commit -m "feat: EditStage — merge/concat/subtitle burn-in"
```

---

## Task 6: 전체 테스트 통과 + push

- [ ] **Step 1: 전체 테스트 실행**

```bash
uv run pytest tests/ -v
```
Expected: 41개 이상 PASS

- [ ] **Step 2: push**

```bash
git push -u origin feat/plan4-image-video-edit
```
