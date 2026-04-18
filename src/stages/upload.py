from loguru import logger
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext, UploadResult
from src.config.settings import Settings
from src.services.youtube_upload import YouTubeUploadService


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

        video_path = ctx.run_dir / ctx.edit.video_path
        thumbnail_path = ctx.run_dir / ctx.thumbnail.image_path

        meta = ctx.script.youtube_meta if ctx.script else None
        title = (meta.title if meta and meta.title else ctx.topic)[:100]
        description = (meta.description if meta and meta.description else "")[:5000]
        tags = (meta.tags if meta and meta.tags else [])[:500]

        svc = YouTubeUploadService(
            client_secret_path=self.settings.youtube_client_secret_path
        )

        logger.info(f"[upload] 영상 업로드 중: {video_path.name}")
        video_id = svc.upload_video(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
        )
        logger.info(f"[upload] 업로드 완료: video_id={video_id}")

        if thumbnail_path.exists():
            logger.info("[upload] 썸네일 업로드 중")
            svc.upload_thumbnail(video_id=video_id, thumbnail_path=thumbnail_path)
            logger.info("[upload] 썸네일 업로드 완료")

        studio_url = f"https://studio.youtube.com/video/{video_id}/edit"
        ctx.upload = UploadResult(video_id=video_id, studio_url=studio_url)
        ctx.completed_stages.append(self.name)
        logger.info(f"[upload] Studio URL: {studio_url}")
        return ctx
