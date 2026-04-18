from pathlib import Path
import pytest
from src.pipeline.context import PipelineContext
from src.config.channel import ChannelConfig


def make_test_ctx(tmp_path: Path) -> PipelineContext:
    run_dir = tmp_path / "runs" / "channel_a" / "test_run"
    run_dir.mkdir(parents=True)
    channel = ChannelConfig(channel_id="channel_a", voice_id="v123")
    return PipelineContext(
        run_id="test_run",
        run_dir=run_dir,
        channel_name="channel_a",
        channel=channel,
        urls=["https://youtube.com/shorts/abc"],
        topic="테스트 주제",
        created_at="2026-04-16T00:00:00Z",
        updated_at="2026-04-16T00:00:00Z",
    )


def test_pipeline_context_json_roundtrip(tmp_path):
    ctx = make_test_ctx(tmp_path)

    json_str = ctx.model_dump_json()
    restored = PipelineContext.model_validate_json(json_str)

    assert restored.run_id == ctx.run_id
    assert restored.topic == ctx.topic
    assert restored.channel.voice_id == "v123"
    assert restored.completed_stages == []
    assert restored.benchmark is None


def test_pipeline_context_completed_stages_survives_roundtrip(tmp_path):
    ctx = make_test_ctx(tmp_path)
    ctx.completed_stages.append("benchmark")

    json_str = ctx.model_dump_json()
    restored = PipelineContext.model_validate_json(json_str)

    assert "benchmark" in restored.completed_stages


from src.pipeline.state import CheckpointManager


def test_checkpoint_save_and_load(tmp_path):
    ctx = make_test_ctx(tmp_path)
    ctx.completed_stages = ["benchmark", "script"]

    manager = CheckpointManager()
    manager.save(ctx)

    assert (ctx.run_dir / "pipeline_state.json").exists()

    restored = manager.load(ctx.run_dir)
    assert restored.run_id == ctx.run_id
    assert restored.completed_stages == ["benchmark", "script"]
    assert restored.channel.channel_id == "channel_a"


def test_checkpoint_save_updates_timestamp(tmp_path):
    ctx = make_test_ctx(tmp_path)
    original = ctx.updated_at

    CheckpointManager().save(ctx)
    restored = CheckpointManager().load(ctx.run_dir)

    assert restored.updated_at != original


def test_checkpoint_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        CheckpointManager().load(tmp_path / "nonexistent")
