# Plan 4: ImageVideoStage + EditStage 설계

**날짜:** 2026-04-17  
**브랜치:** feat/plan4-image-video-edit (off feat/plan3-tts-storyboard)  
**승인:** Discord "A, 플랜4 진행해줘" — fal.ai 통합 방식

---

## 개요

Plan 3에서 생성된 TTS 오디오·자막과 스토리보드(enhanced_prompt)를 받아,
씬별 이미지→영상을 생성하고 최종 Shorts 영상으로 편집한다.

---

## ImageVideoStage (stage_no = 5)

### 입력
- `ctx.storyboard.scenes`: `EnhancedScene(enhanced_prompt, negative_prompt)` 목록

### 처리 (asyncio Semaphore, 기본 N=3 병렬)
1. **fal.ai Flux** → 씬별 이미지 생성 → `{run_dir}/image_video/scene_{n}.png`
2. **fal.ai Kling** → 이미지→영상 → `{run_dir}/image_video/scene_{n}.mp4`
3. 씬 단위 체크포인트: 파일 존재 시 스킵

### 출력
```python
ctx.image_video = ImageVideoResult(scenes=[SceneMedia(...)])
```

---

## EditStage (stage_no = 6)

### 입력
- `ctx.tts.scenes`: `SceneTTS(audio_path, srt_path)`
- `ctx.image_video.scenes`: `SceneMedia(video_path)`

### 처리 (FFmpeg 서브프로세스)
1. 씬별: video clip + audio 합성 → `{run_dir}/edit/scene_{n}_merged.mp4`
2. 전체 씬 이어붙이기 (concat) → `{run_dir}/edit/concat.mp4`
3. SRT 자막 burn-in → `{run_dir}/final_shorts.mp4`

### 출력
```python
ctx.edit = EditResult(video_path="final_shorts.mp4")
```

---

## 신규 파일

| 파일 | 역할 |
|------|------|
| `src/services/fal.py` | fal.ai Flux + Kling API 클라이언트 (키 1개) |
| `src/services/ffmpeg.py` | FFmpeg asyncio 서브프로세스 래퍼 |
| `src/stages/image_video.py` | ImageVideoStage 구현 (스텁 교체) |
| `src/stages/edit.py` | EditStage 구현 (스텁 교체) |
| `tests/unit/test_image_video_stage.py` | ImageVideoStage 단위 테스트 |
| `tests/unit/test_edit_stage.py` | EditStage 단위 테스트 |

---

## Settings 변경

`flux_api_key` / `kling_api_key` → **`fal_api_key`** 로 통합  
(fal.ai는 단일 키로 Flux·Kling 모두 사용)

---

## fal.ai API

- **Flux 이미지 생성:** `fal-ai/flux/schnell`  
  - 입력: `prompt`, `negative_prompt`, `image_size: "portrait_4_3"`
  - 출력: `images[0].url` → 다운로드 후 PNG 저장
- **Kling 이미지→영상:** `fal-ai/kling-video/v1/standard/image-to-video`  
  - 입력: `image_url` (fal.ai 업로드 후 URL), `prompt`, `duration: "5"`
  - 출력: `video.url` → 다운로드 후 MP4 저장
- **Python SDK:** `fal-client` 패키지 (`fal_client.subscribe`)

---

## 테스트 전략

- `fal.py`: `httpx` mock으로 API 응답 테스트
- `ffmpeg.py`: `asyncio.create_subprocess_exec` mock
- `ImageVideoStage`: `FalService` mock, 파일 존재 시 스킵 검증
- `EditStage`: `FFmpegService` mock, concat·자막 burn-in 호출 순서 검증
