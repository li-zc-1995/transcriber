from src.cli import build_parser, default_model_name


def test_cli_defaults_to_faster_whisper_large_v3_turbo() -> None:
    parser = build_parser()
    args = parser.parse_args(["https://b23.tv/MJoM0cX"])

    assert args.backend == "faster-whisper"
    assert args.model == "large-v3-turbo"
    assert args.device == "auto"
    assert args.compute_type == "int8"
    assert default_model_name() == "large-v3-turbo"


def test_cli_still_accepts_openai_whisper_fallback() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--backend",
            "openai-whisper",
            "--model",
            "small",
            "https://b23.tv/MJoM0cX",
        ]
    )

    assert args.backend == "openai-whisper"
    assert args.model == "small"
