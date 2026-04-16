# 유튜브 쇼츠 자동화 시스템 설계 문서

> CLI 기반 · 8단계 완전 자동화 파이프라인 · 멀티채널 확장 지원

---

## 사용자 시나리오

```
# 실행
$ python run.py \
    --urls "https://youtube.com/shorts/xxx" "https://youtube.com/shorts/yyy" \
    --topic "카페인 과다복용 부작용 5가지" \
    --style "dark cinematic"        # 선택사항 (없으면 자동분석)
    --duration 60                   # 선택사항 (없으면 기본 60초)
    --channel "channel_a"           # 채널 config 선택

# 흐름
① 벤치마킹 + 전략 리포트 자동 생성
② [사람 승인] 전략 리포트 확인 → y 입력 시 계속 진행
③ 대본 ~ 업로드 전 단계 자동 실행
④ YouTube 비공개 업로드 완료 → 사람이 수동으로 공개
```

---

## 핵심 데이터 구조

모든 단계는 아래 하나의 JSON을 중심으로 연결됩니다.

```json
// script.json (파이프라인 중심 데이터)
{
  "meta": {
    "topic": "카페인 과다복용 부작용 5가지",
    "duration_target": 60,
    "format": "list",
    "visual_style": "dark cinematic, Korean aesthetic"
  },
  "title": "영상 제목",
  "hook": "첫 3초 후킹 멘트",
  "scenes": [
    {
      "scene_no": 1,
      "narration": "나레이션 텍스트 (1~2문장)",
      "image_prompt": "강화된 이미지 프롬프트 (영어)",
      "duration_sec": 5,
      "caption": "자막 텍스트"
    }
  ],
  "cta": "마지막 행동 유도 멘트",
  "thumbnail_prompt": "썸네일 이미지 생성 프롬프트"
}
```

---

## 채널 Config 구조

멀티채널 운영을 위한 채널별 설정 파일입니다.

```json
// channels/channel_a/config.json
{
  "channel_id": "channel_a",
  "youtube_channel_id": "UCxxxxxxx",
  "voice_id": "elevenlabs_voice_id",
  "visual_style_presets": {
    "default": "dark cinematic, moody lighting, Korean aesthetic",
    "bright": "minimal white, clean modern, bright lighting",
    "retro": "film grain, vintage color grading, nostalgic"
  },
  "subtitle_style": {
    "font": "NanumGothicBold",
    "size": 52,
    "color": "white",
    "outline": 3,
    "position": "bottom_third"
  },
  "bgm_enabled": true,
  "bgm_volume": 0.15
}
```

---

## 단계별 상세 설계

### ① 벤치마킹 단계

**INPUT:** 래퍼런스 URL 1~3개 + 주제/소재 텍스트  
**OUTPUT:** `benchmark_{hash}.json` + CLI 전략 리포트

#### 처리 흐름

```
1. YouTube Data API
   → 영상 메타데이터 수집 (제목, 설명, 조회수, 좋아요)
   → 자막 추출 (captions API)
   → 댓글 수집 (좋아요순 상위 50개)

2. Perplexity / 웹 검색
   → 소재 관련 최신 데이터/통계/사례 수집 (추가 리서치)
   → 핵심 주장 팩트체크 (신뢰할 수 있는 출처 확인)

3. Claude API → 종합 분석
   → 스크립트 + 댓글 → 패턴 추출
   → 전략 리포트 생성
```

#### 벤치마킹 분석 프롬프트

```
당신은 유튜브 쇼츠 전략가입니다.
아래 영상 데이터를 분석해서 제작 전략을 도출하세요.

[영상 자막]
{transcript}

[상위 댓글 (좋아요순)]
{top_comments}

[추가 리서치 결과]
{research_results}

[소재]
{topic}

아래 JSON 형식으로만 응답하세요:
{
  "hook_pattern": "후킹 방식 설명 (질문형/충격형/공감형 등)",
  "story_structure": "영상 구조 설명 (리스트형/나레이션형 등)",
  "tone": "톤 설명 (예: 차분하고 신뢰감 있는, 긴장감 있는)",
  "pacing": "fast | medium | slow",
  "visual_style": "비주얼 스타일 설명",
  "transition_style": "트랜지션 스타일",
  "bgm_present": true | false,
  "bgm_style": "BGM 스타일 설명",
  "subtitle_style": {
    "position": "top | middle | bottom_third",
    "emphasis": "키워드 강조 방식"
  },
  "positive_from_comments": ["시청자가 좋아한 요소들"],
  "negative_from_comments": ["시청자가 싫어한 요소들"],
  "fact_check_results": [
    { "claim": "주장", "verified": true, "source": "출처" }
  ],
  "additional_data": ["대본에 활용할 통계/사례들"],
  "recommended_format": "list | narration | interview",
  "recommended_duration": 60,
  "strategy_summary": "전체 영상 전략 요약 (3~5줄)"
}
```

#### 재사용 로직

```python
cache_key = hashlib.md5("|".join(sorted(urls)).encode()).hexdigest()[:8]
cache_path = f"cache/benchmark_{cache_key}.json"

if os.path.exists(cache_path):
    print("✅ 캐시된 벤치마킹 결과 사용")
    return load_json(cache_path)
else:
    result = run_benchmark(urls, topic)
    save_json(cache_path, result)
    return result
```

---

### ② 대본 단계

**INPUT:** `benchmark.json` + 소재 텍스트 + 목표시간(기본 60초)  
**OUTPUT:** `script.json`

#### 대본 생성 프롬프트

```
당신은 유튜브 쇼츠 스크립트 작가입니다.

[벤치마킹 전략]
- 포맷: {recommended_format}
- 톤: {tone}
- 후킹 패턴: {hook_pattern}
- 시청자가 좋아한 요소: {positive_from_comments}
- 시청자가 싫어한 요소: {negative_from_comments}
- 검증된 팩트/데이터: {fact_check_results}
- 추가 리서치 데이터: {additional_data}

[소재]
{topic}

[목표 길이]
{duration_target}초 이내

위 전략을 반영해 쇼츠 스크립트를 아래 JSON으로만 출력하세요.
preamble 없이 JSON만 출력합니다.

{
  "title": "YouTube 업로드용 제목 (CTR 최적화)",
  "hook": "첫 3초 후킹 멘트 (질문 또는 충격적 사실)",
  "scenes": [
    {
      "scene_no": 1,
      "narration": "나레이션 텍스트 (1~2문장, 자연스러운 구어체)",
      "image_prompt": "이 장면 이미지 설명 (영어, 구체적으로)",
      "duration_sec": 5,
      "caption": "화면에 표시할 자막 텍스트 (15자 이내)"
    }
  ],
  "cta": "마지막 행동 유도 멘트",
  "thumbnail_prompt": "썸네일용 이미지 프롬프트 (영어)",
  "youtube_meta": {
    "title": "업로드 제목",
    "description": "영상 설명 (200자 내외, 해시태그 포함)",
    "tags": ["태그1", "태그2", "태그3"]
  }
}

조건:
- 씬 수: 전체 duration에 맞게 자동 조정 (씬당 평균 5초)
- 첫 씬은 반드시 후킹으로 시작
- narration은 TTS로 읽힐 것을 감안해 자연스러운 구어체로
- caption은 핵심 키워드만 (15자 이내)
- image_prompt는 9:16 세로 비율 기준으로 작성
```

---

### ③ 음성 + 자막 단계

**INPUT:** `script.json` + `benchmark.json` (톤/스타일)  
**OUTPUT:** `scene_N.mp3` + `scene_N.srt` + `subtitle_style.json`

#### 보이스 매칭 로직

```python
# benchmark.json의 tone → ElevenLabs 보이스 자동 매칭
VOICE_MAP = {
    "차분하고_신뢰감": "voice_id_calm",
    "긴장감_있는": "voice_id_intense",
    "밝고_에너지": "voice_id_energetic",
    "낮고_중후한": "voice_id_deep",
}

def match_voice(tone: str) -> str:
    # Claude API로 tone → 가장 적합한 보이스 매칭
    ...
```

#### TTS 자동화

```python
for scene in scenes:
    audio = elevenlabs.generate(
        text=scene["narration"],
        voice=matched_voice_id,
        model="eleven_multilingual_v2",
        voice_settings={"stability": 0.5, "similarity_boost": 0.8}
    )
    save(f"output/scene_{scene.scene_no:02d}.mp3")

    # Whisper로 SRT 생성
    result = whisper.transcribe(f"output/scene_{scene.scene_no:02d}.mp3")
    srt = format_srt(result, max_chars_per_line=15)
    save(f"output/scene_{scene.scene_no:02d}.srt")
```

---

### ④ 스토리보드 단계

**INPUT:** `script.json` (image_prompt 배열) + 비주얼 스타일  
**OUTPUT:** 강화된 이미지 프롬프트 배열

#### 비주얼 스타일 우선순위

```python
def resolve_visual_style(cli_style, channel_preset, benchmark_style):
    # 1순위: CLI 직접 입력
    if cli_style:
        return cli_style
    # 2순위: 채널 config 프리셋
    if channel_preset:
        return config["visual_style_presets"][channel_preset]
    # 3순위: 래퍼런스 자동 분석
    return benchmark_style
```

#### 이미지 프롬프트 강화 프롬프트

```
아래 장면 설명을 Flux 이미지 생성에 최적화된 프롬프트로 변환하세요.

원본 설명: {scene.image_prompt}
비주얼 스타일: {visual_style}
씬 번호: {scene_no} / 전체 {total_scenes}

JSON으로만 응답:
{
  "enhanced_prompt": "{강화된 프롬프트}, vertical 9:16 format,
    {visual_style}, cinematic composition,
    no text, no watermark, high quality, 4k",
  "negative_prompt": "blurry, low quality, text, watermark,
    horizontal format, distorted faces"
}
```

---

### ⑤ 이미지 + 영상 단계

**INPUT:** 강화된 이미지 프롬프트 배열  
**OUTPUT:** `scene_N.png` + `scene_N.mp4`

#### Flux → Kling 자동화

```python
for scene in scenes:
    # Flux로 이미지 생성
    img = flux_api.generate(
        prompt=scene["enhanced_prompt"],
        negative_prompt=scene["negative_prompt"],
        width=1080, height=1920,  # 9:16
        steps=28, guidance=3.5
    )
    save(f"output/scene_{scene.scene_no:02d}.png")

    # Kling AI로 영상 변환
    video = kling_api.image_to_video(
        image_path=f"output/scene_{scene.scene_no:02d}.png",
        duration=scene["duration_sec"],
        motion_strength=0.5,   # 과도한 움직임 방지
        prompt=f"subtle motion, {visual_style}"
    )
    save(f"output/scene_{scene.scene_no:02d}.mp4")
```

---

### ⑥ 편집 단계

**INPUT:** `scene_N.mp4` + `scene_N.mp3` + `scene_N.srt` + `benchmark.json`  
**OUTPUT:** `final_shorts.mp4`

#### FFmpeg 자동화

```python
# 1. 씬별 mp4 + mp3 싱크
for i, scene in enumerate(scenes):
    cmd = f"""
    ffmpeg -i scene_{i:02d}.mp4 -i scene_{i:02d}.mp3
      -c:v copy -c:a aac
      -map 0:v:0 -map 1:a:0
      clip_{i:02d}.mp4
    """

# 2. 트랜지션 적용 (래퍼런스 분석값)
#    benchmark["transition_style"] → xfade 파라미터 매핑
TRANSITION_MAP = {
    "cut":      {"type": "fade",     "duration": 0},
    "fade":     {"type": "fade",     "duration": 0.3},
    "slide":    {"type": "slideleft","duration": 0.3},
    "zoom":     {"type": "zoom",     "duration": 0.4},
}

# 3. 전체 씬 concat + 트랜지션
concat_with_transitions(clips, transition_style)

# 4. BGM 삽입 (래퍼런스 분석값에 따라 자동 판단)
if benchmark["bgm_present"]:
    add_bgm(bgm_file, volume=config["bgm_volume"])

# 5. 자막 오버레이 (하단 1/3 고정)
add_subtitles(
    video="concat.mp4",
    srt_files=all_srts,
    font=config["subtitle_style"]["font"],
    size=config["subtitle_style"]["size"],
    color="white",
    outline=3,
    y_position="h*2/3"   # 하단 1/3 지점
)
```

---

### ⑦ 썸네일 단계

**INPUT:** `script.json` (thumbnail_prompt) + 래퍼런스 썸네일 스타일  
**OUTPUT:** `thumbnail.png` (1080x1920)

#### 썸네일 프롬프트 강화

```
래퍼런스 썸네일 스타일: {benchmark["visual_style"]}
제목: {script["title"]}
후킹 멘트: {script["hook"]}
기본 프롬프트: {script["thumbnail_prompt"]}

썸네일 최적화 프롬프트로 변환하세요.
조건:
- 강렬한 감정/표정 또는 임팩트 있는 장면
- 큰 텍스트 영역 확보 (상단 or 하단 1/3)
- 클릭을 유도하는 고대비 컬러
- 9:16 세로 비율 (1080x1920)
- no text in image (텍스트는 별도로 오버레이)
```

---

### ⑧ 내보내기 + 업로드 단계

**INPUT:** `final_shorts.mp4` + `thumbnail.png` + `script.json` (youtube_meta)  
**OUTPUT:** YouTube 비공개 업로드 완료

#### 업로드 자동화

```python
# 메타데이터 CLI 출력 → 사용자 최종 수정 기회 제공
print("\n📋 업로드 메타데이터 확인:")
print(f"제목: {meta['title']}")
print(f"설명: {meta['description']}")
print(f"태그: {', '.join(meta['tags'])}")

confirm = input("\n수정 없이 업로드할까요? (y/수정할 항목 입력): ")
if confirm != "y":
    meta = manual_edit(meta)

# YouTube Data API v3로 비공개 업로드
youtube.videos().insert(
    part="snippet,status",
    body={
        "snippet": {
            "title":       meta["title"],
            "description": meta["description"],
            "tags":        meta["tags"],
            "categoryId":  "22"
        },
        "status": {
            "privacyStatus":            "private",   # 비공개 저장
            "selfDeclaredMadeForKids":  False
        }
    },
    media_body=MediaFileUpload(
        "output/final_shorts.mp4",
        mimetype="video/mp4",
        chunksize=-1,
        resumable=True
    )
).execute()

# 썸네일 업로드
youtube.thumbnails().set(
    videoId=video_id,
    media_body=MediaFileUpload("output/thumbnail.png")
).execute()

print(f"\n✅ 비공개 업로드 완료!")
print(f"👉 https://studio.youtube.com/video/{video_id}/edit")
print(f"   공개 준비되면 위 링크에서 수동으로 공개하세요.")
```

---

## 전체 파이프라인 요약

```
CLI 입력
  --urls [URL 1~3개]
  --topic "소재"
  --channel "채널명"
  --style "스타일" (선택)
  --duration 60 (선택)
        │
        ▼
① 벤치마킹 ──────────────────────── benchmark_{hash}.json 캐시
  YouTube API → 자막/댓글 수집
  Perplexity  → 팩트체크 + 리서치
  Claude API  → 패턴 분석 + 전략 도출
        │
        ▼
  [사람 승인] 전략 리포트 확인 → y
        │
        ▼
② 대본 생성 ─────────────────────── script.json
  Claude API → 포맷 자동선택 + 씬 생성
             + 이미지 프롬프트 + 메타데이터
        │
        ▼
③ 음성 + 자막 ───────────────────── scene_N.mp3 / scene_N.srt
  ElevenLabs → 보이스 자동 매칭 + TTS
  Whisper    → SRT 생성
        │
        ▼
④ 스토리보드 ────────────────────── 강화된 프롬프트 배열
  Claude API → 이미지 프롬프트 강화
  (스타일: 직접입력 > 프리셋 > 자동분석)
        │
        ▼
⑤ 이미지 + 영상 ─────────────────── scene_N.png / scene_N.mp4
  Flux API   → 이미지 생성 (9:16)
  Kling AI   → 전체 씬 영상화
        │
        ▼
⑥ 편집 ──────────────────────────── final_shorts.mp4
  FFmpeg     → 싱크 + 트랜지션 + BGM + 자막 (하단 1/3)
        │
        ▼
⑦ 썸네일 ────────────────────────── thumbnail.png
  Flux API   → 래퍼런스 스타일 분석 후 자동 생성
        │
        ▼
⑧ 업로드 ────────────────────────── YouTube 비공개 저장
  메타데이터 사용자 최종 확인/수정
  YouTube Data API v3 → 비공개 업로드
        │
        ▼
  [사람] Studio에서 수동 공개
```

---

## 기술 스택 요약

| 단계 | 도구 | 비고 |
|------|------|------|
| 벤치마킹 | YouTube Data API v3 | 자막/댓글 수집 |
| 팩트체크/리서치 | Perplexity API | 최신 데이터 검색 |
| 분석/대본/프롬프트 | Claude API (claude-sonnet-4) | 핵심 AI 엔진 |
| TTS | ElevenLabs API | 보이스 자동 매칭 |
| 자막 | OpenAI Whisper | 타임스탬프 추출 |
| 이미지 생성 | Flux API | 9:16 고화질 |
| 영상 변환 | Kling AI API | 이미지→mp4 |
| 편집 | FFmpeg | 싱크/트랜지션/자막 |
| 업로드 | YouTube Data API v3 | 비공개 업로드 |

---

## 다음 단계 제안

1. **① 벤치마킹 모듈** 먼저 구현 (YouTube API + Claude 분석)
2. **② 대본 모듈** 구현 및 프롬프트 튜닝
3. **③~⑥ 미디어 파이프라인** 순차 구현
4. **채널 config** 설계 후 멀티채널 확장
