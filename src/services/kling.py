import base64
import httpx
from pathlib import Path

_FAL_BASE = "https://fal.run"
_KLING_MODEL = "fal-ai/kling-video/v1.6/standard/image-to-video"


class KlingService:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def generate_video(
        self,
        scene_no: int,
        image_path: Path,
        prompt: str,
        run_dir: Path,
        duration: int = 5,
    ) -> str:
        out_dir = run_dir / "image_video"
        out_dir.mkdir(parents=True, exist_ok=True)
        video_path = out_dir / f"scene_{scene_no}.mp4"

        image_bytes = image_path.read_bytes()
        image_data_url = f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}"

        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{_FAL_BASE}/{_KLING_MODEL}",
                headers={
                    "Authorization": f"Key {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "image_url": image_data_url,
                    "prompt": prompt,
                    "duration": str(duration),
                    "aspect_ratio": "9:16",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        video_url = data["video"]["url"]
        async with httpx.AsyncClient(timeout=120.0) as client:
            vid_resp = await client.get(video_url)
            vid_resp.raise_for_status()
            video_path.write_bytes(vid_resp.content)

        return str(video_path.relative_to(run_dir)).replace("\\", "/")
