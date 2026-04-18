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

    assert s1.ran is False
    assert s2.ran is False
    assert s3.ran is True
    assert result.status == "done"


@pytest.mark.asyncio
async def test_new_runner_instance_honours_checkpoint(tmp_path):
    """새 PipelineRunner 인스턴스로 재시작해도 체크포인트 반영"""
    checkpoint = CheckpointManager()
    ctx = make_ctx(tmp_path)

    s1 = TrackingStage("s1", 1)
    runner1 = PipelineRunner(stages=[s1], checkpoint=checkpoint)
    await runner1.run(ctx)

    restored = checkpoint.load(ctx.run_dir)
    s1_new = TrackingStage("s1", 1)
    s2_new = TrackingStage("s2", 2)
    runner2 = PipelineRunner(stages=[s1_new, s2_new], checkpoint=checkpoint)
    await runner2.run(restored)

    assert s1_new.ran is False
    assert s2_new.ran is True
