from loguru import logger
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext, TTSResult
from src.config.settings import Settings
from src.services.elevenlabs import ElevenLabsService


class TTSStage(BaseStage):
    name = "tts"
    stage_no = 3

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.script is None:
            raise ValueError("script 결과가 없습니다. ScriptStage를 먼저 실행하세요.")

        elevenlabs = ElevenLabsService(api_key=self.settings.elevenlabs_api_key)
        voice_id = ctx.channel.voice_id

        logger.info(f"[tts] ElevenLabs TTS 시작 (voice_id={voice_id})")
        scenes = []
        for scene in ctx.script.scenes:
            scene_tts = await elevenlabs.generate_scene_tts(
                scene_no=scene.scene_no,
                narration=scene.narration,
                voice_id=voice_id,
                run_dir=ctx.run_dir,
            )
            scenes.append(scene_tts)
            logger.debug(f"[tts] 씬 {scene.scene_no} 완료")

        ctx.tts = TTSResult(scenes=scenes, voice_id=voice_id)
        logger.success(f"[tts] 완료: {len(scenes)}개 씬")
        return ctx
