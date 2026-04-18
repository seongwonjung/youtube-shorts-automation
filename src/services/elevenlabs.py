import base64
import httpx
from pathlib import Path
from src.pipeline.context import SceneTTS


_BASE_URL = "https://api.elevenlabs.io"


def _build_srt(words: list[str], start_times: list[float], end_times: list[float]) -> str:
    """단어 목록과 타임스탬프로 SRT 자막을 생성한다."""
    lines = []
    idx = 1
    chunk_words: list[str] = []
    chunk_start: float | None = None
    chunk_end: float | None = None

    for word, start, end in zip(words, start_times, end_times):
        if chunk_start is None:
            chunk_start = start
        chunk_words.append(word)
        chunk_end = end

        if len(chunk_words) >= 5:
            lines.append(_srt_entry(idx, chunk_start, chunk_end, " ".join(chunk_words)))
            idx += 1
            chunk_words = []
            chunk_start = None
            chunk_end = None

    if chunk_words and chunk_start is not None and chunk_end is not None:
        lines.append(_srt_entry(idx, chunk_start, chunk_end, " ".join(chunk_words)))

    return "\n\n".join(lines)


def _srt_entry(idx: int, start: float, end: float, text: str) -> str:
    return f"{idx}\n{_ts(start)} --> {_ts(end)}\n{text}"


def _ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


class ElevenLabsService:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def generate_scene_tts(
        self,
        scene_no: int,
        narration: str,
        voice_id: str,
        run_dir: Path,
    ) -> SceneTTS:
        tts_dir = run_dir / "tts"
        tts_dir.mkdir(parents=True, exist_ok=True)

        audio_path = tts_dir / f"scene_{scene_no}.mp3"
        srt_path = tts_dir / f"scene_{scene_no}.srt"

        async with httpx.AsyncClient(base_url=_BASE_URL, timeout=60.0) as client:
            resp = await client.post(
                f"/v1/text-to-speech/{voice_id}/with-timestamps",
                headers={"xi-api-key": self._api_key},
                json={
                    "text": narration,
                    "model_id": "eleven_multilingual_v2",
                    "output_format": "mp3_44100_128",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        audio_bytes = base64.b64decode(data["audio_base64"])
        audio_path.write_bytes(audio_bytes)

        alignment = data.get("alignment", {})
        words = alignment.get("chars", [])
        starts = alignment.get("char_start_times_seconds", [])
        ends = alignment.get("char_end_times_seconds", [])
        srt_content = _build_srt(words, starts, ends)
        srt_path.write_text(srt_content, encoding="utf-8")

        rel = str(tts_dir.relative_to(run_dir))
        return SceneTTS(
            scene_no=scene_no,
            audio_path=f"{rel}/scene_{scene_no}.mp3".replace("\\", "/"),
            srt_path=f"{rel}/scene_{scene_no}.srt".replace("\\", "/"),
        )
