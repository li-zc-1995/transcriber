from pathlib import Path


def test_pyinstaller_spec_bundles_local_ffmpeg_candidate() -> None:
    spec_text = Path("transcriber.spec").read_text(encoding="utf-8")

    assert "ffmpeg_candidates" in spec_text
    assert "verification_outputs" in spec_text
    assert 'binaries.append((str(ffmpeg_candidate), "."))' in spec_text
