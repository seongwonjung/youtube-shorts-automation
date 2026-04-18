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
