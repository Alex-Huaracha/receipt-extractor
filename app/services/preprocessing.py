"""Turns an uploaded file (JPG, PNG or PDF) into images ready for a vision model."""

from dataclasses import dataclass
from io import BytesIO

import pypdfium2 as pdfium
from PIL import Image, ImageOps, UnidentifiedImageError

# Safety limits: they reject absurd inputs, they are not the expected size of a receipt.
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_PDF_PAGES = 3
# Fewer pixels means fewer tokens; 2048 px still keeps small print readable.
MAX_IMAGE_SIDE = 2048
JPEG_QUALITY = 90

SUPPORTED_IMAGE_FORMATS = {"JPEG", "PNG"}


class InvalidFileError(ValueError):
    """The file cannot be processed."""


class FileTooLargeError(InvalidFileError):
    pass


class UnsupportedFormatError(InvalidFileError):
    pass


@dataclass(frozen=True)
class PreparedImage:
    data: bytes
    mime_type: str


def prepare(file: bytes) -> list[PreparedImage]:
    """Returns one image per page. The type is detected from the content, not the file name."""
    if len(file) > MAX_FILE_SIZE:
        raise FileTooLargeError(f"File exceeds {MAX_FILE_SIZE // (1024 * 1024)} MB")
    if file.startswith(b"%PDF-"):
        pages = _render_pdf(file)
    else:
        pages = [_open_image(file)]
    return [_encode(_shrink(page)) for page in pages]


def _open_image(file: bytes) -> Image.Image:
    try:
        image = Image.open(BytesIO(file))
        if image.format not in SUPPORTED_IMAGE_FORMATS:
            raise UnsupportedFormatError(f"Unsupported image format: {image.format}")
        image.load()
    except (UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise UnsupportedFormatError("File is not a supported image or PDF") from exc
    except OSError as exc:
        raise InvalidFileError("Image is corrupted or truncated") from exc
    # Phones store photos sideways and record the rotation in EXIF.
    return ImageOps.exif_transpose(image)


def _render_pdf(file: bytes) -> list[Image.Image]:
    try:
        pdf = pdfium.PdfDocument(file)
    except pdfium.PdfiumError as exc:
        raise InvalidFileError("PDF is corrupted or password protected") from exc
    try:
        # Rejected instead of truncated: the total is usually on the last page.
        if len(pdf) > MAX_PDF_PAGES:
            raise InvalidFileError(f"PDF has {len(pdf)} pages, the limit is {MAX_PDF_PAGES}")
        images = []
        for page in pdf:
            # Render straight at the final size so a huge page never allocates a huge bitmap.
            scale = MAX_IMAGE_SIDE / max(page.get_size())
            images.append(page.render(scale=scale).to_pil())
        return images
    finally:
        pdf.close()


def _shrink(image: Image.Image) -> Image.Image:
    image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)
    return image


def _encode(image: Image.Image) -> PreparedImage:
    if image.mode in ("RGBA", "LA", "P"):
        # Transparent pixels would turn black; text is printed on white paper.
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        image = background
    else:
        image = image.convert("RGB")
    buffer = BytesIO()
    # A fresh JPEG carries no metadata, so the EXIF (including GPS location) is dropped.
    image.save(buffer, "JPEG", quality=JPEG_QUALITY)
    return PreparedImage(data=buffer.getvalue(), mime_type="image/jpeg")
