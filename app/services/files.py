"""Private local file storage and bounded text extraction."""

import csv
import io
import json
import re
import struct
import uuid
import zipfile
import zlib
from pathlib import Path
from xml.etree import ElementTree

from fastapi import UploadFile

from app.core.config import get_settings

ALLOWED = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def safe_filename(filename: str) -> str:
    name = Path(filename).name.replace("\\", "_").strip()
    if not name or name in {".", ".."}:
        raise ValueError("Invalid filename")
    return name[:255]


def storage_path(key: str) -> Path:
    # Keys are generated UUIDs, never derived from display filenames.
    if not re.fullmatch(r"[0-9a-f-]{36}", key):
        raise ValueError("Invalid storage identifier")
    return Path(get_settings().file_storage_dir).resolve() / key


async def read_upload(upload: UploadFile) -> bytes:
    limit = get_settings().upload_max_bytes
    data = bytearray()
    while chunk := await upload.read(1024 * 1024):
        data.extend(chunk)
        if len(data) > limit:
            raise ValueError("File exceeds the configured size limit")
    if not data:
        raise ValueError("File is empty")
    return bytes(data)


def validate_bytes(filename: str, data: bytes) -> tuple[str, str]:
    ext = Path(filename).suffix.lower()
    mime = ALLOWED.get(ext)
    if not mime:
        raise ValueError("Supported formats are PDF, DOCX, TXT, Markdown, CSV, and JSON")
    if ext == ".pdf" and not data.startswith(b"%PDF-"):
        raise ValueError("File content is not a valid PDF")
    if ext in IMAGE_EXTENSIONS:
        image_max = get_settings().image_max_bytes
        if len(data) > image_max:
            raise ValueError("Image exceeds the configured size limit")
        width, height = _image_dimensions(ext, data)
        if (
            width < 1
            or height < 1
            or width > 20000
            or height > 20000
            or width * height > 40_000_000
        ):
            raise ValueError("Image dimensions exceed the supported limit")
    if ext == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                info = archive.getinfo("word/document.xml")
                if info.file_size > get_settings().extracted_text_max_chars * 8:
                    raise ValueError("DOCX content exceeds the extraction limit")
        except (zipfile.BadZipFile, KeyError) as exc:
            raise ValueError("File content is not a valid DOCX") from exc
    return mime, ext


def _image_dimensions(ext: str, data: bytes) -> tuple[int, int]:
    if ext == ".png":
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("File content is not a valid PNG image")
        offset = 8
        width = height = 0
        saw_image_data = saw_end = False
        while offset + 12 <= len(data):
            length = int.from_bytes(data[offset : offset + 4], "big")
            chunk_end = offset + 12 + length
            if chunk_end > len(data):
                break
            name = data[offset + 4 : offset + 8]
            chunk = data[offset + 8 : offset + 8 + length]
            expected_crc = int.from_bytes(data[offset + 8 + length : chunk_end], "big")
            if zlib.crc32(name + chunk) & 0xFFFFFFFF != expected_crc:
                raise ValueError("PNG image data is corrupted")
            if name == b"IHDR" and length == 13:
                width, height = struct.unpack(">II", chunk[:8])
            elif name == b"IDAT":
                saw_image_data = True
            elif name == b"IEND":
                saw_end = True
                break
            offset = chunk_end
        if not saw_image_data or not saw_end:
            raise ValueError("PNG image is incomplete")
        return width, height
    if not data.startswith(b"\xff\xd8\xff") or not data.endswith(b"\xff\xd9"):
        raise ValueError("File content is not a valid JPEG image")
    index = 2
    while index + 4 <= len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        index += 2
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        length = int.from_bytes(data[index : index + 2], "big")
        if length < 2 or index + length > len(data):
            break
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            height = int.from_bytes(data[index + 3 : index + 5], "big")
            width = int.from_bytes(data[index + 5 : index + 7], "big")
            return width, height
        index += length
    raise ValueError("JPEG image dimensions could not be validated")


def extract_pages(ext: str, data: bytes) -> list[tuple[int | None, str]]:
    if ext in IMAGE_EXTENSIONS:
        return []
    if ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported")
        if len(reader.pages) > 500:
            raise ValueError("PDF contains too many pages")
        return [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
    if ext == ".docx":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            xml = ElementTree.fromstring(archive.read("word/document.xml"))
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs = ["".join(node.itertext()) for node in xml.findall(".//w:p", ns)]
        return [(None, "\n".join(p for p in paragraphs if p.strip()))]
    text = data.decode("utf-8-sig")
    if ext == ".json":
        return [(None, json.dumps(json.loads(text), ensure_ascii=False, indent=2))]
    if ext == ".csv":
        rows = list(csv.reader(io.StringIO(text)))
        if len(rows) > 10000:
            raise ValueError("CSV contains too many rows")
        return [(None, "\n".join(" | ".join(row) for row in rows))]
    return [(None, text)]


def chunks(pages: list[tuple[int | None, str]]) -> list[tuple[int, int | None, str]]:
    maximum = get_settings().extracted_text_max_chars
    content = "\n".join(text for _, text in pages)
    if not content.strip():
        raise ValueError("No extractable text was found in this document")
    if len(content) > maximum:
        content = content[:maximum]
    result = []
    offset = 0
    for page, text in pages:
        for start in range(0, len(text), 2000):
            result.append((len(result), page, text[start : start + 2000]))
        offset += len(text)
    return result


def make_key() -> str:
    return str(uuid.uuid4())
