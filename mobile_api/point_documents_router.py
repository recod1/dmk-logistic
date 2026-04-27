from __future__ import annotations

import logging
import mimetypes
import uuid
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from mobile_api.auth import get_current_driver, get_current_user
from mobile_api.db import get_db
from mobile_api.models import Point, PointDocumentImage, Route, User
from mobile_api.roles import ADMIN_ACCESS_ROLES, ROUTE_MANAGER_ROLES, RoleCode, normalize_role_code
from mobile_api.settings import mobile_settings

router = APIRouter(tags=["point-documents"])

logger = logging.getLogger(__name__)

MAX_FILES_PER_UPLOAD = 20
MAX_FILE_BYTES = 12 * 1024 * 1024


def _upload_root() -> Path:
    root = Path(mobile_settings.mobile_upload_root)
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _can_user_view_document(db: Session, user: User, row: PointDocumentImage) -> bool:
    point = db.get(Point, row.point_id)
    if point is None:
        return False
    route = db.get(Route, point.route_id)
    if route is None:
        return False
    try:
        role = normalize_role_code(user.role_code)
    except ValueError:
        return False
    if role == RoleCode.DRIVER:
        return route.assigned_user_id == user.id
    if role in ROUTE_MANAGER_ROLES or role in ADMIN_ACCESS_ROLES:
        return True
    return False


def _thumb_filename_for(stored_name: str) -> str:
    return f"t_{stored_name}"


def _try_write_thumbnail_jpeg(full_path: Path, body: bytes) -> None:
    """Сжатое превью рядом с оригиналом (надёжнее отображение в списках и слабых сетях)."""
    try:
        from PIL import Image
    except ImportError:
        logger.debug("Pillow not installed; skipping document thumbnail")
        return
    try:
        im = Image.open(BytesIO(body))
        im = im.convert("RGB")
        im.thumbnail((512, 512), Image.Resampling.LANCZOS)
        buf = BytesIO()
        im.save(buf, format="JPEG", quality=85, optimize=True)
        thumb_path = full_path.parent / _thumb_filename_for(full_path.name)
        thumb_path.write_bytes(buf.getvalue())
    except Exception as exc:
        logger.warning("point document thumbnail failed: %s", exc)


def _validate_image_content_type(content_type: str) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    if not ct.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image uploads are allowed",
        )
    return ct


@router.post("/v1/mobile/points/{point_id}/documents")
async def upload_point_documents(
    point_id: int,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_driver),
) -> dict:
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files")
    if len(files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Too many files")

    point = db.get(Point, point_id)
    if point is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Point not found")
    route = db.get(Route, point.route_id)
    if route is None or route.assigned_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Point is not available")
    if point.status not in {"load", "docs", "success"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Documents can only be uploaded at the gates / documents stage",
        )

    root = _upload_root()
    sub = root / str(point_id)
    sub.mkdir(parents=True, exist_ok=True)

    created_ids: list[int] = []
    for upload in files:
        ctype = upload.content_type or mimetypes.guess_type(upload.filename or "")[0] or "application/octet-stream"
        ctype = _validate_image_content_type(ctype)
        body = await upload.read()
        if len(body) > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large (max {MAX_FILE_BYTES} bytes)",
            )
        ext = mimetypes.guess_extension(ctype) or ".jpg"
        if ext == ".jpe":
            ext = ".jpg"
        fname = f"{uuid.uuid4().hex}{ext}"
        full_path = sub / fname
        full_path.write_bytes(body)
        _try_write_thumbnail_jpeg(full_path, body)
        rel = f"{point_id}/{fname}"
        row = PointDocumentImage(
            point_id=point.id,
            route_id=point.route_id,
            uploaded_by_user_id=current_user.id,
            storage_path=rel,
            content_type=ctype,
            file_size=len(body),
        )
        db.add(row)
        db.flush()
        created_ids.append(row.id)

    db.commit()
    return {"file_ids": created_ids}


@router.get("/v1/point-documents/{image_id}/file")
def download_point_document(
    image_id: int,
    thumb: bool = Query(default=False, description="Если true — отдать JPEG-превью при наличии, иначе полный файл"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    row = db.get(PointDocumentImage, image_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if not _can_user_view_document(db, current_user, row):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    root = _upload_root()
    full_path = (root / row.storage_path).resolve()
    try:
        full_path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path") from exc
    if not full_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing on server")

    serve_path = full_path
    media_type = row.content_type or "application/octet-stream"
    if thumb:
        thumb_path = full_path.parent / _thumb_filename_for(full_path.name)
        if thumb_path.is_file():
            serve_path = thumb_path
            media_type = "image/jpeg"

    headers = {"Cache-Control": "private, max-age=86400"}
    return FileResponse(
        path=str(serve_path),
        media_type=media_type,
        filename=serve_path.name,
        headers=headers,
    )
