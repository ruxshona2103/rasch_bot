from pathlib import Path

MEDIA_ROOT = Path(__file__).resolve().parent.parent / "media" / "tests"


def test_media_dir(test_id: int) -> Path:
    directory = MEDIA_ROOT / str(test_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def save_question_png(test_id: int, order_num: int, png_bytes: bytes) -> Path:
    path = test_media_dir(test_id) / f"{order_num}.png"
    path.write_bytes(png_bytes)
    return path
