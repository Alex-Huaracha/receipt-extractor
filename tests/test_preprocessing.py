from io import BytesIO

import pytest
from PIL import Image

from app.services import preprocessing
from app.services.preprocessing import (
    MAX_IMAGE_SIDE,
    FileTooLargeError,
    InvalidFileError,
    UnsupportedFormatError,
    prepare,
)

ORIENTATION = 0x0112
ROTATED_90 = 6


def make_image(size=(300, 100), mode="RGB", color="white", fmt="JPEG", exif=None) -> bytes:
    buffer = BytesIO()
    image = Image.new(mode, size, color)
    if exif is not None:
        image.save(buffer, fmt, exif=exif)
    else:
        image.save(buffer, fmt)
    return buffer.getvalue()


def make_pdf(pages: int) -> bytes:
    images = [Image.new("RGB", (595, 842), "white") for _ in range(pages)]
    buffer = BytesIO()
    images[0].save(buffer, "PDF", save_all=True, append_images=images[1:])
    return buffer.getvalue()


def open_result(data: bytes) -> Image.Image:
    return Image.open(BytesIO(data))


def test_jpeg_returns_one_jpeg_image():
    result = prepare(make_image())
    assert len(result) == 1
    assert result[0].mime_type == "image/jpeg"
    assert open_result(result[0].data).format == "JPEG"


def test_photo_is_rotated_using_exif():
    exif = Image.Exif()
    exif[ORIENTATION] = ROTATED_90
    result = prepare(make_image(size=(300, 100), exif=exif))
    assert open_result(result[0].data).size == (100, 300)


def test_metadata_is_removed():
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"  # camera make, stands in for any personal metadata
    result = prepare(make_image(exif=exif))
    assert len(open_result(result[0].data).getexif()) == 0


def test_large_image_is_shrunk_keeping_proportions():
    result = prepare(make_image(size=(4000, 3000)))
    assert open_result(result[0].data).size == (MAX_IMAGE_SIDE, 1536)


def test_small_image_is_not_enlarged():
    result = prepare(make_image(size=(800, 600)))
    assert open_result(result[0].data).size == (800, 600)


def test_transparent_png_gets_a_white_background():
    result = prepare(make_image(mode="RGBA", color=(0, 0, 0, 0), fmt="PNG"))
    assert open_result(result[0].data).getpixel((0, 0)) == (255, 255, 255)


def test_pdf_returns_one_image_per_page():
    result = prepare(make_pdf(pages=2))
    assert len(result) == 2
    assert max(open_result(result[0].data).size) == MAX_IMAGE_SIDE


def test_pdf_over_the_page_limit_is_rejected():
    with pytest.raises(InvalidFileError, match="pages"):
        prepare(make_pdf(pages=preprocessing.MAX_PDF_PAGES + 1))


def test_corrupted_pdf_is_rejected():
    with pytest.raises(InvalidFileError):
        prepare(b"%PDF-1.7 not really a pdf")


def test_unsupported_image_format_is_rejected():
    with pytest.raises(UnsupportedFormatError):
        prepare(make_image(fmt="GIF"))


def test_unknown_file_is_rejected():
    with pytest.raises(UnsupportedFormatError):
        prepare(b"just some text")


def test_file_over_the_size_limit_is_rejected(monkeypatch):
    monkeypatch.setattr(preprocessing, "MAX_FILE_SIZE", 100)
    with pytest.raises(FileTooLargeError):
        prepare(make_image())
