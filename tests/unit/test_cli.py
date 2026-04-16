import pytest
from src.cli.main import parse_args


def test_parse_new_run_args():
    args = parse_args([
        "--urls", "https://youtube.com/shorts/abc", "https://youtube.com/shorts/xyz",
        "--topic", "카페인 과다복용 부작용 5가지",
        "--channel", "channel_a",
        "--duration", "60",
    ])
    assert args.urls == ["https://youtube.com/shorts/abc", "https://youtube.com/shorts/xyz"]
    assert args.topic == "카페인 과다복용 부작용 5가지"
    assert args.channel == "channel_a"
    assert args.duration == 60
    assert args.style is None
    assert args.resume is None


def test_parse_resume_args():
    args = parse_args(["--resume", "runs/channel_a/20260416_143022_abc123"])
    assert args.resume == "runs/channel_a/20260416_143022_abc123"
    assert args.urls is None


def test_parse_requires_topic_with_urls():
    with pytest.raises(SystemExit):
        parse_args(["--urls", "https://youtube.com/shorts/abc"])


def test_parse_urls_and_resume_mutually_exclusive():
    with pytest.raises(SystemExit):
        parse_args([
            "--urls", "https://youtube.com/shorts/abc",
            "--resume", "runs/channel_a/run1",
            "--topic", "test",
        ])
