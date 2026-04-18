# Plan 5: ThumbnailStage + UploadStage + Docker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement ThumbnailStage (Flux 이미지 생성) + UploadStage (YouTube OAuth2 업로드) + Dockerfile에 ffmpeg 추가.

**Architecture:** ThumbnailStage는 FluxService를 재사용해 `thumbnail_prompt`로 이미지를 생성한다. UploadStage는 기존 `youtube.py`에 OAuth2 업로드 메서드를 추가해 영상과 썸네일을 업로드한다. Dockerfile에는 ffmpeg 바이너리 설치가 누락되어 있어 추가한다.

**Tech Stack:** Python 3.12, httpx, google-api-python-client, google-auth-oauthlib, fal.ai Flux, pytest-asyncio

---

## File Map

| 경로 | 작업 |
|------|------|
| `src/stages/thumbnail.py` | 스텁 → 완전 구현 |
| `src/stages/upload.py` | 스텁 → 완전 구현 |
| `src/services/youtube.py` | `upload_video()` + `set_thumbnail()` 추가 |
| `tests/unit/test_thumbnail_stage.py` | 신규 |
| `tests/unit/test_upload_stage.py` | 신규 |
| `Dockerfile` | `ffmpeg` 설치 추가 |

---

## Task 1: feat/plan5-thumbnail-upload 브랜치 생성

**Files:** (없음 — git 작업만)

- [ ] **Step 1: 새 브랜치 생성**

```bash
cd C:/Users/jsjsw/AppData/Local/Temp/plan4-worktree
git checkout -b feat/plan5-thumbnail-upload
```

Expected: `Switched to a new branch 'feat/plan5-thumbnail-upload'`

---

## Task 2: ThumbnailStage TDD

**Files:**
- Create: `tests/unit/test_thumbnail_stage.py`
- Modify: `src/stages/thumbnail.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/unit/test_thumbnail_stage.py` 파일을 생성한다:

```python
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from src.stages.thumbnail import ThumbnailStage
from src.pipeline.context import (
    PipelineContext, ScriptResult, YouTubeMeta, ThumbnailResult,
)
from src.config.channel import ChannelConfig
from src.config.settings import Settings


def _make_settings():
    return Settings(
        anthropic_api_key="x",
        elevenlabs_api_key="x",
        youtube_api_key="x",
        flux_api_key="fal-key",
        kling_api_key="fal-key",
    )


def _make_ctx(tmp_path, with_script=True):
    channel = ChannelConfig(channel_id="ch", voice_id="v1", visual_style_presets={})
    ctx = PipelineContext(
        run_id="r1", run_dir=tmp_path, channel_name="test",
        channel=channel, urls=[], topic="test",
    )
    if with_script:
        ctx.script = ScriptResult(
            title="테스트",
            thumbnail_prompt="epic dark cinematic thumbnail",
            youtube_meta=YouTubeMeta(title="테스트", description="설명", tags=["tag1"]),
        )
    return ctx


@pytest.mark.asyncio
async def test_sets_ctx_thumbnail(tmp_path):
    ctx = _make_ctx(tmp_path)
    stage = ThumbnailStage(settings=_make_settings())

    with patch("src.stages.thumbnail.FluxService") as MockFlux:
        flux_inst = MockFlux.return_value
        flux_inst.generate_image = AsyncMock(return_value="thumbnail/thumbnail.png")
        result = await stage.run(ctx)

    assert result.thumbnail is not None
    assert result.thumbnail.image_path == "thumbnail/thumbnail.png"


@pytest.mark.asyncio
async def test_raises_if_no_script(tmp_path):
    ctx = _make_ctx(tmp_path, with_script=False)
    stage = ThumbnailStage(settings=_make_settings())
    with pytest.raises(ValueError, match="script"):
        await stage.run(ctx)


@pytest.mark.asyncio
async def test_skips_existing_thumbnail(tmp_path):
    ctx = _make_ctx(tmp_path)
    stage = ThumbnailStage(settings=_make_settings())

    thumb_dir = tmp_path / "thumbnail"
    thumb_dir.mkdir()
    (thumb_dir / "thumbnail.png").write_bytes(b"fake")

    with patch("src.stages.thumbnail.FluxService") as MockFlux:
        flux_inst = MockFlux.return_value
        flux_inst.generate_image = AsyncMock(return_value="thumbnail/thumbnail.png")
        result = await stage.run(ctx)

    flux_inst.generate_image.assert_not_called()
    assert result.thumbnail is not None
    assert result.thumbnail.image_path == "thumbnail/thumbnail.png"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd C:/Users/jsjsw/AppData/Local/Temp/plan4-worktree
uv run pytest tests/unit/test_thumbnail_stage.py -v 2>&1 | head -30
```

Expected: ImportError 또는 FAILED (스텁이므로)

- [ ] **Step 3: ThumbnailStage 구현**

`src/stages/thumbnail.py`를 다음으로 교체한다:

```python
from loguru import logger
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext, ThumbnailResult
from src.config.settings import Settings
from src.services.flux import FluxService


class ThumbnailStage(BaseStage):
    name = "thumbnail"
    stage_no = 7

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.script is None:
            raise ValueError("script 결과가 없습니다. ScriptStage를 먼저 실행하세요.")

        thumb_rel = "thumbnail/thumbnail.png"
        thumb_abs = ctx.run_dir / thumb_rel

        if thumb_abs.exists():
            logger.debug("[thumbnail] 캐시 사용")
            ctx.thumbnail = ThumbnailResult(image_path=thumb_rel)
            return ctx

        flux = FluxService(api_key=self.settings.flux_api_key)
        logger.info("[thumbnail] 썸네일 생성 중")
        image_rel = await flux.generate_image(
            scene_no=0,
            prompt=ctx.script.thumbnail_prompt,
            negative_prompt="blurry, low quality, text overlay",
            run_dir=ctx.run_dir,
            subdir="thumbnail",
            filename="thumbnail.png",
        )
        ctx.thumbnail = ThumbnailResult(image_path=image_rel)
        logger.success("[thumbnail] 완료")
        return ctx
```

- [ ] **Step 4: FluxService에 subdir/filename 파라미터 추가**

`src/services/flux.py`의 `generate_image` 시그니처를 다음으로 수정한다:

```python
import httpx
from pathlib import Path

_FAL_BASE = "https://fal.run"
_FLUX_MODEL = "fal-ai/flux-pro"


class FluxService:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def generate_image(
        self,
        scene_no: int,
        prompt: str,
        negative_prompt: str,
        run_dir: Path,
        subdir: str = "image_video",
        filename: str | None = None,
    ) -> str:
        out_dir = run_dir / subdir
        out_dir.mkdir(parents=True, exist_ok=True)
        fname = filename if filename else f"scene_{scene_no}.png"
        image_path = out_dir / fname

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{_FAL_BASE}/{_FLUX_MODEL}",
                headers={
                    "Authorization": f"Key {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "image_size": "portrait_4_3",
                    "num_inference_steps": 28,
                    "guidance_scale": 3.5,
                    "num_images": 1,
                    "enable_safety_checker": False,
                    "output_format": "png",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        image_url = data["images"][0]["url"]
        async with httpx.AsyncClient(timeout=60.0) as client:
            img_resp = await client.get(image_url)
            img_resp.raise_for_status()
            image_path.write_bytes(img_resp.content)

        return str(image_path.relative_to(run_dir)).replace("\\", "/")
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
cd C:/Users/jsjsw/AppData/Local/Temp/plan4-worktree
uv run pytest tests/unit/test_thumbnail_stage.py -v
```

Expected: 3 passed

- [ ] **Step 6: 전체 테스트 회귀 확인**

```bash
uv run pytest tests/unit/ -v 2>&1 | tail -5
```

Expected: 41 passed (기존 테스트 전부 통과)

- [ ] **Step 7: 커밋**

```bash
cd C:/Users/jsjsw/AppData/Local/Temp/plan4-worktree
git add src/stages/thumbnail.py src/services/flux.py tests/unit/test_thumbnail_stage.py
git commit -m "feat: ThumbnailStage + FluxService subdir/filename 파라미터 추가"
```

---

## Task 3: YouTubeService에 업로드 메서드 추가

**Files:**
- Modify: `src/services/youtube.py`

- [ ] **Step 1: youtube.py에 업로드 메서드 추가**

`src/services/youtube.py` 파일 끝에 다음을 추가한다 (기존 YouTubeService 클래스 안에):

```python
    def _get_authenticated_service(self, token_path: str, client_secret_path: str):
        """OAuth2 인증된 YouTube 서비스 객체를 반환한다."""
        import os
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
        creds = None

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, "w") as f:
                f.write(creds.to_json())

        return build("youtube", "v3", credentials=creds)

    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list[str],
        token_path: str,
        client_secret_path: str,
    ) -> str:
        """YouTube에 영상을 업로드하고 video_id를 반환한다."""
        from googleapiclient.http import MediaFileUpload

        youtube = self._get_authenticated_service(token_path, client_secret_path)
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": "22",
            },
            "status": {"privacyStatus": "private"},
        }
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            _, response = request.next_chunk()
        return response["id"]

    def set_thumbnail(
        self,
        video_id: str,
        thumbnail_path: str,
        token_path: str,
        client_secret_path: str,
    ) -> None:
        """업로드된 영상에 썸네일을 설정한다."""
        from googleapiclient.http import MediaFileUpload

        youtube = self._get_authenticated_service(token_path, client_secret_path)
        media = MediaFileUpload(thumbnail_path, mimetype="image/png")
        youtube.thumbnails().set(videoId=video_id, media_body=media).execute()
```

- [ ] **Step 2: 커밋**

```bash
cd C:/Users/jsjsw/AppData/Local/Temp/plan4-worktree
git add src/services/youtube.py
git commit -m "feat: YouTubeService에 upload_video + set_thumbnail 추가"
```

---

## Task 4: UploadStage TDD

**Files:**
- Create: `tests/unit/test_upload_stage.py`
- Modify: `src/stages/upload.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/unit/test_upload_stage.py` 파일을 생성한다:

```python
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.stages.upload import UploadStage
from src.pipeline.context import (
    PipelineContext, EditResult, ThumbnailResult, ScriptResult,
    YouTubeMeta, UploadResult,
)
from src.config.channel import ChannelConfig
from src.config.settings import Settings


def _make_settings():
    return Settings(
        anthropic_api_key="x",
        elevenlabs_api_key="x",
        youtube_api_key="x",
        flux_api_key="fal-key",
        kling_api_key="fal-key",
    )


def _make_ctx(tmp_path, with_edit=True, with_thumbnail=True, with_script=True):
    channel = ChannelConfig(channel_id="ch", voice_id="v1", visual_style_presets={})
    ctx = PipelineContext(
        run_id="r1", run_dir=tmp_path, channel_name="test",
        channel=channel, urls=[], topic="test",
    )
    if with_edit:
        video_file = tmp_path / "final_shorts.mp4"
        video_file.write_bytes(b"video")
        ctx.edit = EditResult(video_path="final_shorts.mp4")
    if with_thumbnail:
        thumb_dir = tmp_path / "thumbnail"
        thumb_dir.mkdir(exist_ok=True)
        (thumb_dir / "thumbnail.png").write_bytes(b"img")
        ctx.thumbnail = ThumbnailResult(image_path="thumbnail/thumbnail.png")
    if with_script:
        ctx.script = ScriptResult(
            title="테스트",
            youtube_meta=YouTubeMeta(title="제목", description="설명", tags=["tag"]),
        )
    return ctx


@pytest.mark.asyncio
async def test_sets_ctx_upload(tmp_path):
    ctx = _make_ctx(tmp_path)
    stage = UploadStage(settings=_make_settings())

    with patch("src.stages.upload.YouTubeService") as MockYT:
        yt_inst = MockYT.return_value
        yt_inst.upload_video = MagicMock(return_value="abc123")
        yt_inst.set_thumbnail = MagicMock()

        result = await stage.run(ctx)

    assert result.upload is not None
    assert result.upload.video_id == "abc123"
    assert "abc123" in result.upload.studio_url


@pytest.mark.asyncio
async def test_raises_if_no_edit(tmp_path):
    ctx = _make_ctx(tmp_path, with_edit=False)
    stage = UploadStage(settings=_make_settings())
    with pytest.raises(ValueError, match="edit"):
        await stage.run(ctx)


@pytest.mark.asyncio
async def test_raises_if_no_thumbnail(tmp_path):
    ctx = _make_ctx(tmp_path, with_thumbnail=False)
    stage = UploadStage(settings=_make_settings())
    with pytest.raises(ValueError, match="thumbnail"):
        await stage.run(ctx)
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd C:/Users/jsjsw/AppData/Local/Temp/plan4-worktree
uv run pytest tests/unit/test_upload_stage.py -v 2>&1 | head -30
```

Expected: FAILED (스텁이므로)

- [ ] **Step 3: UploadStage 구현**

`src/stages/upload.py`를 다음으로 교체한다:

```python
from loguru import logger
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext, UploadResult
from src.config.settings import Settings
from src.services.youtube import YouTubeService


class UploadStage(BaseStage):
    name = "upload"
    stage_no = 8

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.edit is None:
            raise ValueError("edit 결과가 없습니다. EditStage를 먼저 실행하세요.")
        if ctx.thumbnail is None:
            raise ValueError("thumbnail 결과가 없습니다. ThumbnailStage를 먼저 실행하세요.")

        meta = ctx.script.youtube_meta if ctx.script else None
        title = meta.title if meta else ctx.topic
        description = meta.description if meta else ""
        tags = meta.tags if meta else []

        video_abs = str(ctx.run_dir / ctx.edit.video_path)
        thumb_abs = str(ctx.run_dir / ctx.thumbnail.image_path)
        token_path = "secrets/token.json"  # CWD 기준 (로컬 및 Docker 모두 project root가 CWD)
        secret_path = self.settings.youtube_client_secret_path

        yt = YouTubeService(api_key=self.settings.youtube_api_key)
        logger.info("[upload] YouTube 업로드 시작")
        video_id = yt.upload_video(
            video_path=video_abs,
            title=title,
            description=description,
            tags=tags,
            token_path=token_path,
            client_secret_path=secret_path,
        )
        logger.info(f"[upload] 영상 업로드 완료: {video_id}")

        yt.set_thumbnail(
            video_id=video_id,
            thumbnail_path=thumb_abs,
            token_path=token_path,
            client_secret_path=secret_path,
        )
        logger.info("[upload] 썸네일 설정 완료")

        studio_url = f"https://studio.youtube.com/video/{video_id}/edit"
        ctx.upload = UploadResult(video_id=video_id, studio_url=studio_url)
        logger.success(f"[upload] 완료: {studio_url}")
        return ctx
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd C:/Users/jsjsw/AppData/Local/Temp/plan4-worktree
uv run pytest tests/unit/test_upload_stage.py -v
```

Expected: 3 passed

- [ ] **Step 5: 전체 테스트 회귀 확인**

```bash
uv run pytest tests/unit/ -v 2>&1 | tail -5
```

Expected: 47 passed

- [ ] **Step 6: 커밋**

```bash
cd C:/Users/jsjsw/AppData/Local/Temp/plan4-worktree
git add src/stages/upload.py tests/unit/test_upload_stage.py
git commit -m "feat: UploadStage 구현 + TDD 테스트"
```

---

## Task 5: Dockerfile 완성 (ffmpeg 추가)

**Files:**
- Modify: `Dockerfile`

- [ ] **Step 1: Dockerfile에 ffmpeg 설치 추가**

`Dockerfile`을 다음으로 교체한다:

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

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

- [ ] **Step 2: 커밋**

```bash
cd C:/Users/jsjsw/AppData/Local/Temp/plan4-worktree
git add Dockerfile
git commit -m "chore: Dockerfile에 ffmpeg 설치 추가"
```

---

## Task 6: 브랜치 push

- [ ] **Step 1: 원격 push**

```bash
cd C:/Users/jsjsw/AppData/Local/Temp/plan4-worktree
git push -u origin feat/plan5-thumbnail-upload
```

Expected: `Branch 'feat/plan5-thumbnail-upload' set up to track remote branch`
