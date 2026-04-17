import re
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi


class YouTubeService:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    @staticmethod
    def extract_video_id(url: str) -> str:
        patterns = [
            r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})",
        ]
        for pattern in patterns:
            m = re.search(pattern, url)
            if m:
                return m.group(1)
        raise ValueError(f"YouTube video ID를 추출할 수 없습니다: {url}")

    async def fetch_video_data(self, url: str) -> dict:
        video_id = self.extract_video_id(url)
        youtube = build("youtube", "v3", developerKey=self._api_key)

        video_resp = youtube.videos().list(
            part="snippet,statistics",
            id=video_id,
        ).execute()

        items = video_resp.get("items", [])
        if not items:
            return {"video_id": video_id, "title": "", "description": "",
                    "view_count": 0, "like_count": 0, "comments": [], "transcript": ""}

        snippet = items[0]["snippet"]
        stats = items[0].get("statistics", {})

        comments = []
        try:
            comments_resp = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=50,
                order="relevance",
            ).execute()
            for item in comments_resp.get("items", []):
                text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
                comments.append(text)
        except Exception:
            pass

        transcript = ""
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(
                video_id, languages=["ko", "en"]
            )
            transcript = " ".join(t["text"] for t in transcript_list)
        except Exception:
            pass

        return {
            "video_id": video_id,
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comments": comments,
            "transcript": transcript,
        }
