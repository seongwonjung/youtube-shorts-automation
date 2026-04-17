import json
import anthropic
from src.pipeline.context import BenchmarkResult, ScriptResult


_BENCHMARK_SYSTEM = """당신은 YouTube Shorts 콘텐츠 전략가입니다.
YouTube 영상 데이터를 분석하여 반드시 아래 JSON 스키마를 따르는 BenchmarkResult를 반환하세요.
응답은 JSON만 포함해야 합니다. 추가 텍스트나 마크다운 코드블록을 쓰지 마세요.

BenchmarkResult 스키마:
{
  "hook_pattern": "string",
  "story_structure": "string",
  "tone": "string",
  "pacing": "string",
  "visual_style": "string",
  "transition_style": "string",
  "bgm_present": boolean,
  "bgm_style": "string",
  "subtitle_style": {"position": "string", "emphasis": "string"},
  "positive_from_comments": ["string"],
  "negative_from_comments": ["string"],
  "fact_check_results": [],
  "additional_data": ["string"],
  "recommended_format": "string",
  "recommended_duration": integer,
  "strategy_summary": "string"
}"""

_SCRIPT_SYSTEM = """당신은 YouTube Shorts 스크립트 작가입니다.
BenchmarkResult와 주제를 바탕으로 반드시 아래 JSON 스키마를 따르는 ScriptResult를 반환하세요.
응답은 JSON만 포함해야 합니다. 추가 텍스트나 마크다운 코드블록을 쓰지 마세요.

ScriptResult 스키마:
{
  "title": "string",
  "hook": "string",
  "scenes": [
    {
      "scene_no": integer,
      "narration": "string",
      "image_prompt": "string",
      "duration_sec": integer,
      "caption": "string"
    }
  ],
  "cta": "string",
  "thumbnail_prompt": "string",
  "youtube_meta": {
    "title": "string",
    "description": "string",
    "tags": ["string"]
  }
}"""


class ClaudeService:
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)

    async def analyze_benchmark(self, videos: list[dict]) -> BenchmarkResult:
        videos_text = json.dumps(videos, ensure_ascii=False, indent=2)
        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=[{
                "type": "text",
                "text": _BENCHMARK_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{
                "role": "user",
                "content": f"다음 YouTube 영상 데이터를 분석하세요:\n\n{videos_text}",
            }],
        )
        text = next(b.text for b in response.content if b.type == "text")
        return BenchmarkResult.model_validate_json(text)

    async def generate_script(
        self,
        benchmark: BenchmarkResult,
        topic: str,
        visual_style: str,
        duration: int,
    ) -> ScriptResult:
        user_content = (
            f"주제: {topic}\n"
            f"목표 길이: {duration}초\n"
            f"비주얼 스타일: {visual_style}\n\n"
            f"벤치마크 분석 결과:\n{benchmark.model_dump_json(indent=2)}"
        )
        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=[{
                "type": "text",
                "text": _SCRIPT_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{
                "role": "user",
                "content": user_content,
            }],
        )
        text = next(b.text for b in response.content if b.type == "text")
        return ScriptResult.model_validate_json(text)
