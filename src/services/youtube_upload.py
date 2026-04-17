import json
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
_TOKEN_PATH = "secrets/youtube_token.json"


class YouTubeUploadService:
    def __init__(self, client_secret_path: str) -> None:
        self._client_secret_path = client_secret_path

    def _get_credentials(self) -> Credentials:
        token_path = Path(_TOKEN_PATH)
        creds: Credentials | None = None

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), _SCOPES)

        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                self._client_secret_path, _SCOPES
            )
            creds = flow.run_local_server(port=0)

        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())
        return creds

    def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        category_id: str = "22",
        privacy_status: str = "private",
    ) -> str:
        creds = self._get_credentials()
        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=256 * 1024,
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            _, response = request.next_chunk()

        return response["id"]

    def upload_thumbnail(self, video_id: str, thumbnail_path: Path) -> None:
        creds = self._get_credentials()
        youtube = build("youtube", "v3", credentials=creds)

        media = MediaFileUpload(
            str(thumbnail_path),
            mimetype="image/png",
        )
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=media,
        ).execute()
