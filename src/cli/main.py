import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="YouTube Shorts 자동화 파이프라인")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--urls", nargs="+", metavar="URL",
        help="래퍼런스 YouTube URL (1~3개)",
    )
    group.add_argument(
        "--resume", metavar="RUN_DIR",
        help="실패한 파이프라인 재시작 (예: runs/channel_a/20260416_143022_abc123)",
    )
    parser.add_argument("--topic", help="영상 소재 (--urls 사용 시 필수)")
    parser.add_argument("--channel", default="channel_a", help="채널 이름 (기본: channel_a)")
    parser.add_argument("--style", help="비주얼 스타일 (선택)")
    parser.add_argument("--duration", type=int, default=60, help="목표 길이 초 (기본: 60)")
    parser.add_argument(
        "--from-stage", dest="from_stage",
        help="특정 스테이지부터 강제 재실행 (--resume과 함께 사용)",
    )
    return parser


def parse_args(args=None):
    parser = build_parser()
    parsed = parser.parse_args(args)
    if parsed.urls and not parsed.topic:
        parser.error("--urls 사용 시 --topic 필수")
    return parsed
