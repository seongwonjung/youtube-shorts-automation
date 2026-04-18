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
