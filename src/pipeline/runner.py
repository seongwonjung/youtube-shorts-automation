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
