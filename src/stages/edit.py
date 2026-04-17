import shutil
from pathlib import Path
from loguru import logger
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext, EditResult
from src.config.settings import Settings
from src.services import ffmpeg as ffmpeg_svc


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

        tts_map = {s.scene_no: s for s in ctx.tts.scenes}
        iv_map = {s.scene_no: s for s in ctx.image_video.scenes}
        scene_nos = sorted(iv_map.keys())

        edit_dir = ctx.run_dir / "edit"
        edit_dir.mkdir(parents=True, exist_ok=True)

        muxed_clips: list[Path] = []
        for scene_no in scene_nos:
            iv = iv_map[scene_no]
            video_path = ctx.run_dir / iv.video_path
            out_clip = edit_dir / f"scene_{scene_no}_muxed.mp4"

            if scene_no in tts_map:
                audio_path = ctx.run_dir / tts_map[scene_no].audio_path
                logger.info(f"[edit] 씬 {scene_no} 비디오+오디오 합성")
                await ffmpeg_svc.mux_video_audio(video_path, audio_path, out_clip)
            else:
                shutil.copy2(video_path, out_clip)
                logger.debug(f"[edit] 씬 {scene_no} 오디오 없음, 비디오만 복사")

            muxed_clips.append(out_clip)

        logger.info("[edit] 씬 이어붙이기")
        concat_path = edit_dir / "concat.mp4"
        await ffmpeg_svc.concat_videos(muxed_clips, concat_path)

        final_path = ctx.run_dir / "final_shorts.mp4"

        srt_path: Path | None = None
        if tts_map:
            first_srt = ctx.run_dir / tts_map[scene_nos[0]].srt_path
            if first_srt.exists():
                srt_path = first_srt

        if srt_path:
            logger.info("[edit] 자막 burn-in")
            await ffmpeg_svc.burn_subtitles(concat_path, srt_path, final_path)
        else:
            shutil.copy2(concat_path, final_path)

        ctx.edit = EditResult(video_path="final_shorts.mp4")
        logger.success(f"[edit] 완료: {final_path}")
        return ctx
