from datetime import datetime, timezone
from pathlib import Path
from src.pipeline.context import PipelineContext


class CheckpointManager:
    def save(self, ctx: PipelineContext) -> None:
        ctx.updated_at = datetime.now(timezone.utc).isoformat()
        path = Path(ctx.run_dir) / "pipeline_state.json"
        path.write_text(ctx.model_dump_json(indent=2), encoding="utf-8")

    def load(self, run_dir: Path) -> PipelineContext:
        path = run_dir / "pipeline_state.json"
        if not path.exists():
            raise FileNotFoundError(f"체크포인트 없음: {path}")
        return PipelineContext.model_validate_json(
            path.read_text(encoding="utf-8")
        )
