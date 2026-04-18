import pytest
from pathlib import Path
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext
from src.config.channel import ChannelConfig
from src.pipeline.runner import PipelineRunner
from src.pipeline.state import CheckpointManager


def make_ctx(tmp_path: Path) -> PipelineContext:
    run_dir = tmp_path / "runs" / "ch" / "run1"
    run_dir.mkdir(parents=True)
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


class DummyStage(BaseStage):
    name = "dummy"
    stage_no = 1

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        return ctx


def test_base_stage_can_skip_false_initially(tmp_path):
    stage = DummyStage()
    ctx = make_ctx(tmp_path)
    assert stage.can_skip(ctx) is False


def test_base_stage_can_skip_true_when_in_completed(tmp_path):
    stage = DummyStage()
    ctx = make_ctx(tmp_path)
    ctx.completed_stages.append("dummy")
    assert stage.can_skip(ctx) is True


@pytest.mark.asyncio
async def test_base_stage_run_returns_ctx(tmp_path):
    stage = DummyStage()
    ctx = make_ctx(tmp_path)
    result = await stage.run(ctx)
    assert result is ctx


class CountingStage(BaseStage):
    def __init__(self, name: str, no: int) -> None:
        self.name = name
        self.stage_no = no
        self.run_count = 0

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        self.run_count += 1
        return ctx


@pytest.mark.asyncio
async def test_runner_executes_all_stages(tmp_path):
    s1 = CountingStage("s1", 1)
    s2 = CountingStage("s2", 2)
    s3 = CountingStage("s3", 3)

    ctx = make_ctx(tmp_path)
    runner = PipelineRunner(stages=[s1, s2, s3], checkpoint=CheckpointManager())
    result = await runner.run(ctx)

    assert s1.run_count == 1
    assert s2.run_count == 1
    assert s3.run_count == 1
    assert result.status == "done"
    assert set(result.completed_stages) == {"s1", "s2", "s3"}


@pytest.mark.asyncio
async def test_runner_skips_completed_stages(tmp_path):
    s1 = CountingStage("s1", 1)
    s2 = CountingStage("s2", 2)

    ctx = make_ctx(tmp_path)
    ctx.completed_stages = ["s1"]  # s1 이미 완료

    runner = PipelineRunner(stages=[s1, s2], checkpoint=CheckpointManager())
    await runner.run(ctx)

    assert s1.run_count == 0  # 스킵됨
    assert s2.run_count == 1  # 실행됨


@pytest.mark.asyncio
async def test_runner_saves_checkpoint_after_each_stage(tmp_path):
    s1 = CountingStage("s1", 1)
    s2 = CountingStage("s2", 2)
    checkpoint = CheckpointManager()

    ctx = make_ctx(tmp_path)
    runner = PipelineRunner(stages=[s1, s2], checkpoint=checkpoint)
    await runner.run(ctx)

    saved = checkpoint.load(ctx.run_dir)
    assert "s1" in saved.completed_stages
    assert "s2" in saved.completed_stages
    assert saved.status == "done"


class FlakyStage(BaseStage):
    """처음 N번 실패, 그 이후 성공하는 테스트용 스테이지"""
    def __init__(self, fail_times: int) -> None:
        self.name = "flaky"
        self.stage_no = 1
        self.fail_times = fail_times
        self.attempt = 0

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        self.attempt += 1
        if self.attempt <= self.fail_times:
            raise RuntimeError(f"의도적 실패 {self.attempt}")
        return ctx


@pytest.mark.asyncio
async def test_runner_retries_on_failure(tmp_path, mocker):
    mocker.patch("src.pipeline.runner.asyncio.sleep")  # 대기시간 제거
    stage = FlakyStage(fail_times=2)  # 처음 2번 실패, 3번째 성공

    ctx = make_ctx(tmp_path)
    runner = PipelineRunner(
        stages=[stage],
        checkpoint=CheckpointManager(),
        max_retries=3,
    )
    result = await runner.run(ctx)

    assert stage.attempt == 3
    assert result.status == "done"


@pytest.mark.asyncio
async def test_runner_saves_failed_status_on_exhausted_retries(tmp_path, mocker):
    mocker.patch("src.pipeline.runner.asyncio.sleep")
    stage = FlakyStage(fail_times=99)  # 항상 실패

    ctx = make_ctx(tmp_path)
    checkpoint = CheckpointManager()
    runner = PipelineRunner(stages=[stage], checkpoint=checkpoint, max_retries=2)

    with pytest.raises(RuntimeError):
        await runner.run(ctx)

    saved = checkpoint.load(ctx.run_dir)
    assert saved.status == "failed"
    assert "의도적 실패" in saved.last_error
