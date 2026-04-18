import asyncio
import shutil
from pathlib import Path


async def _run(args: list[str]) -> None:
    # asyncio.create_subprocess_exec はシェルを使わないためコマンドインジェクション不可
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg 오류 (rc={proc.returncode}): {stderr.decode()}")


def _require_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if path is None:
        raise RuntimeError("ffmpeg 바이너리를 찾을 수 없습니다. ffmpeg를 설치하세요.")
    return path


async def mux_video_audio(video_path: Path, audio_path: Path, out_path: Path) -> None:
    """비디오 클립과 오디오를 합성한다."""
    ff = _require_ffmpeg()
    await _run([
        ff, "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        str(out_path),
    ])


async def concat_videos(clip_paths: list[Path], out_path: Path) -> None:
    """여러 비디오 클립을 순서대로 이어붙인다."""
    ff = _require_ffmpeg()
    concat_list = out_path.parent / "_concat_list.txt"
    lines = [f"file '{p.resolve()}'" for p in clip_paths]
    concat_list.write_text("\n".join(lines), encoding="utf-8")
    try:
        await _run([
            ff, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(out_path),
        ])
    finally:
        concat_list.unlink(missing_ok=True)


async def burn_subtitles(video_path: Path, srt_path: Path, out_path: Path) -> None:
    """영상에 SRT 자막을 burn-in한다."""
    ff = _require_ffmpeg()
    srt_escaped = str(srt_path.resolve()).replace("\\", "/").replace(":", "\\:")
    await _run([
        ff, "-y",
        "-i", str(video_path),
        "-vf", f"subtitles='{srt_escaped}'",
        "-c:a", "copy",
        str(out_path),
    ])
