import asyncio
from loguru import logger
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext, ImageVideoResult, SceneMedia
from src.config.settings import Settings
from src.services.flux import FluxService
from src.services.kling import KlingService


class ImageVideoStage(BaseStage):
    name = "image_video"
    stage_no = 5

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.storyboard is None:
            raise ValueError("storyboard 결과가 없습니다. StoryboardStage를 먼저 실행하세요.")

        flux = FluxService(api_key=self.settings.flux_api_key)
        kling = KlingService(api_key=self.settings.flux_api_key)
        semaphore = asyncio.Semaphore(self.settings.default_concurrency)

        async def process_scene(enhanced_scene) -> SceneMedia:
            async with semaphore:
                scene_no = enhanced_scene.scene_no
                image_rel = f"image_video/scene_{scene_no}.png"
                video_rel = f"image_video/scene_{scene_no}.mp4"
                image_abs = ctx.run_dir / image_rel
                video_abs = ctx.run_dir / video_rel

                if not image_abs.exists():
                    logger.info(f"[image_video] 씬 {scene_no} 이미지 생성 중")
                    image_rel = await flux.generate_image(
                        scene_no=scene_no,
                        prompt=enhanced_scene.enhanced_prompt,
                        negative_prompt=enhanced_scene.negative_prompt,
                        run_dir=ctx.run_dir,
                    )
                    image_abs = ctx.run_dir / image_rel
                else:
                    logger.debug(f"[image_video] 씬 {scene_no} 이미지 캐시 사용")

                if not video_abs.exists():
                    logger.info(f"[image_video] 씬 {scene_no} 영상 생성 중")
                    video_rel = await kling.generate_video(
                        scene_no=scene_no,
                        image_path=image_abs,
                        prompt=enhanced_scene.enhanced_prompt,
                        run_dir=ctx.run_dir,
                    )
                else:
                    logger.debug(f"[image_video] 씬 {scene_no} 영상 캐시 사용")

                return SceneMedia(
                    scene_no=scene_no,
                    image_path=image_rel,
                    video_path=video_rel,
                )

        scenes = await asyncio.gather(
            *[process_scene(s) for s in ctx.storyboard.scenes]
        )
        scenes_sorted = sorted(scenes, key=lambda s: s.scene_no)

        ctx.image_video = ImageVideoResult(scenes=scenes_sorted)
        logger.success(f"[image_video] 완료: {len(scenes_sorted)}개 씬")
        return ctx
