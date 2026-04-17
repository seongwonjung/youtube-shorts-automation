import httpx
from pathlib import Path

_FAL_BASE = "https://fal.run"
_FLUX_MODEL = "fal-ai/flux-pro"


class FluxService:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def generate_image(
        self,
        scene_no: int,
        prompt: str,
        negative_prompt: str,
        run_dir: Path,
    ) -> str:
        out_dir = run_dir / "image_video"
        out_dir.mkdir(parents=True, exist_ok=True)
        image_path = out_dir / f"scene_{scene_no}.png"

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{_FAL_BASE}/{_FLUX_MODEL}",
                headers={
                    "Authorization": f"Key {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "image_size": "portrait_4_3",
                    "num_inference_steps": 28,
                    "guidance_scale": 3.5,
                    "num_images": 1,
                    "enable_safety_checker": False,
                    "output_format": "png",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        image_url = data["images"][0]["url"]
        async with httpx.AsyncClient(timeout=60.0) as client:
            img_resp = await client.get(image_url)
            img_resp.raise_for_status()
            image_path.write_bytes(img_resp.content)

        return str(image_path.relative_to(run_dir)).replace("\\", "/")

    async def generate_thumbnail(
        self,
        prompt: str,
        run_dir: Path,
    ) -> str:
        out_path = run_dir / "thumbnail.png"

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{_FAL_BASE}/{_FLUX_MODEL}",
                headers={
                    "Authorization": f"Key {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "prompt": prompt,
                    "image_size": "landscape_16_9",
                    "num_inference_steps": 28,
                    "guidance_scale": 3.5,
                    "num_images": 1,
                    "enable_safety_checker": False,
                    "output_format": "png",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        image_url = data["images"][0]["url"]
        async with httpx.AsyncClient(timeout=60.0) as client:
            img_resp = await client.get(image_url)
            img_resp.raise_for_status()
            out_path.write_bytes(img_resp.content)

        return str(out_path.relative_to(run_dir)).replace("\\", "/")
