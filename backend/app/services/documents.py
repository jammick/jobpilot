from io import BytesIO
from pathlib import Path

from docx import Document
from fastapi import HTTPException, UploadFile, status
from pypdf import PdfReader

from app.core.config import get_settings

ALLOWED = {".pdf", ".docx"}


def extract_text(raw: bytes, suffix: str) -> str:
    """Extract text without persisting a source file (used by knowledge import too)."""
    if suffix == ".pdf":
        text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(raw)).pages)
    elif suffix == ".docx":
        text = "\n".join(p.text for p in Document(BytesIO(raw)).paragraphs)
    elif suffix in {".md", ".markdown", ".txt"}:
        text = raw.decode("utf-8", errors="replace")
    else:
        raise HTTPException(status_code=400, detail="知识资料仅支持 PDF、DOCX、Markdown 或 TXT")
    return text.strip()


async def save_and_extract(upload: UploadFile) -> tuple[str, str]:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(status_code=400, detail="仅支持 PDF 或 DOCX 格式")
    raw = await upload.read()
    settings = get_settings()
    if not raw or len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"文件不能为空且不得超过 {settings.max_upload_mb}MB")
    try:
        text = extract_text(raw, suffix)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="无法解析该简历文件") from exc
    if len(text.strip()) < 30:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="未提取到足够文本；扫描版 PDF 暂不支持")
    import uuid
    storage_name = f"{uuid.uuid4()}{suffix}"
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    (settings.upload_dir / storage_name).write_bytes(raw)
    return storage_name, text.strip()
