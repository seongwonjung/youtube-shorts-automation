# YouTube Shorts 자동화

레퍼런스 YouTube 영상 URL을 입력하면 벤치마킹 → 스크립트 → TTS → 스토리보드 → 영상 생성 → 편집 → 썸네일 → 업로드까지 전 과정을 자동화하는 파이프라인입니다.

## 주요 특징

- **체크포인트 재시작**: 파이프라인 실패 시 마지막 완료 스테이지부터 재시작
- **채널별 설정**: 채널마다 목소리, 자막 스타일, BGM 등 독립 설정
- **8단계 파이프라인**: Benchmark → Script → TTS → Storyboard → ImageVideo → Edit → Thumbnail → Upload

## 실행 방법

### 사전 준비

```bash
# 의존성 설치 (uv 필요)
uv sync --dev

# 환경 변수 설정
cp .env.example .env
# .env 파일에 API 키 입력
```

### 신규 실행

```bash
uv run python run.py \
  --urls "https://youtube.com/shorts/abc" "https://youtube.com/shorts/xyz" \
  --topic "카페인 과다복용 부작용 5가지" \
  --channel channel_a \
  --duration 60
```

### 실패 후 재시작

```bash
uv run python run.py --resume runs/channel_a/20260416_143022_abc123
```

### 특정 스테이지부터 강제 재실행

```bash
uv run python run.py --resume runs/channel_a/20260416_143022_abc123 --from-stage tts
```

### Docker

```bash
docker compose up
```

### 테스트

```bash
uv run pytest
```

## 아키텍처 (간략)

```
run.py (진입점)
  └─ PipelineRunner          # 스테이지 순차 실행 + 체크포인트 저장
       ├─ BenchmarkStage     # 레퍼런스 영상 분석 (Perplexity)
       ├─ ScriptStage        # 스크립트 생성 (Claude)
       ├─ TTSStage           # 음성 합성 (ElevenLabs)
       ├─ StoryboardStage    # 스토리보드 (Claude)
       ├─ ImageVideoStage    # 이미지/영상 생성 (Flux + Kling)
       ├─ EditStage          # 영상 편집 (FFmpeg)
       ├─ ThumbnailStage     # 썸네일 생성
       └─ UploadStage        # YouTube 업로드

CheckpointManager            # 각 스테이지 완료 후 JSON으로 상태 저장
PipelineContext              # 전체 파이프라인 상태 (Pydantic 모델)
ChannelConfig                # 채널별 설정 (channels/<name>/config.json)
```

## 프로젝트 구조

```
src/
  cli/        # CLI 인터페이스 (argparse)
  pipeline/   # Runner, Context, CheckpointManager
  stages/     # 8개 스테이지 구현
  config/     # Settings (pydantic-settings), ChannelConfig
channels/     # 채널별 config.json
runs/         # 파이프라인 실행 결과 + 체크포인트
tests/
  unit/       # 단위 테스트
  integration/# 재시작 통합 테스트
```

## 환경 변수

| 변수 | 설명 |
|------|------|
| `ANTHROPIC_API_KEY` | Claude API 키 |
| `ELEVENLABS_API_KEY` | ElevenLabs TTS 키 |
| `FLUX_API_KEY` | Flux 이미지 생성 키 |
| `KLING_API_KEY` | Kling 영상 생성 키 |
| `PERPLEXITY_API_KEY` | Perplexity 검색 키 |
| `OPENAI_API_KEY` | OpenAI (Whisper) 키 |
| `MAX_RETRIES` | 스테이지 재시도 횟수 (기본: 3) |
