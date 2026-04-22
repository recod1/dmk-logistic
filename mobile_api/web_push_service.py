from __future__ import annotations

import json
import logging
import threading
from typing import Any

import base64

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from mobile_api.db import SessionLocal
from mobile_api.models import WebPushSubscription
from mobile_api.settings import mobile_settings

logger = logging.getLogger(__name__)

def _base64url_decode(s: str) -> bytes:
    padding = "=" * ((4 - (len(s) % 4)) % 4)
    return base64.urlsafe_b64decode((s + padding).encode("utf-8"))


def _base64_any_decode(s: str) -> bytes:
    s = (s or "").strip()
    if not s:
        return b""
    # First try base64url (common for env vars)
    try:
        return _base64url_decode(s)
    except Exception:
        pass
    # Fallback to standard base64
    padding = "=" * ((4 - (len(s) % 4)) % 4)
    return base64.b64decode((s + padding).encode("utf-8"))


def _safe_b64_any_decode(s: str) -> bytes | None:
    try:
        return _base64_any_decode(s)
    except Exception:
        return None


def _validate_subscription_keys(*, p256dh: str, auth: str) -> tuple[bool, str | None]:
    """
    WebPush subscription keys (per RFC8292/WebPush protocol) are base64url strings:
    - p256dh: uncompressed P-256 public key, 65 bytes
    - auth: 16 bytes
    """
    p = _safe_b64_any_decode(p256dh)
    a = _safe_b64_any_decode(auth)
    if p is None:
        return False, "subscription key p256dh is not valid base64/base64url"
    if a is None:
        return False, "subscription key auth is not valid base64/base64url"
    if len(p) != 65:
        return False, f"subscription key p256dh decoded length is {len(p)} (expected 65)"
    if len(a) != 16:
        return False, f"subscription key auth decoded length is {len(a)} (expected 16)"
    return True, None


def _normalize_vapid_private_key(raw: str) -> str:
    """
    Accept either:
    - PEM (-----BEGIN PRIVATE KEY----- ...)
    - base64url PKCS8 DER (single-line, convenient for env/Portainer)
    and return PEM string for pywebpush.
    """
    raw = (raw or "").strip().strip('"').strip("'")
    if not raw:
        return ""
    # Portainer/compose env often stores PEM as a single line with escaped newlines.
    if "\\n" in raw or "\\r\\n" in raw:
        raw = raw.replace("\\r\\n", "\n").replace("\\n", "\n")
    if "BEGIN" in raw and "END" in raw:
        # If PEM was pasted without newlines, re-wrap it.
        if "\n" not in raw:
            raw = raw.replace("-----BEGIN PRIVATE KEY-----", "-----BEGIN PRIVATE KEY-----\n")
            raw = raw.replace("-----END PRIVATE KEY-----", "\n-----END PRIVATE KEY-----")
        return raw
    try:
        from cryptography.hazmat.primitives import serialization
    except Exception:
        return raw
    try:
        decoded = _base64_any_decode(raw)
        # Some generators provide a "raw" 32-byte private key (scalar).
        # Accept it to avoid PEM hassles in env vars.
        if len(decoded) == 32:
            from cryptography.hazmat.primitives.asymmetric import ec

            private_value = int.from_bytes(decoded, byteorder="big", signed=False)
            key = ec.derive_private_key(private_value, ec.SECP256R1())
        else:
            key = serialization.load_der_private_key(decoded, password=None)
        pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return pem.decode("utf-8")
    except Exception:
        return ""


def send_web_push_to_users(
    *,
    subscriptions: list[tuple[int, str, str, str]],
    title: str,
    body: str,
    notification_id: int | None = None,
) -> None:
    """
    subscriptions: list of (subscription_id, endpoint, p256dh, auth)
    """
    if not mobile_settings.vapid_public_key or not mobile_settings.vapid_private_key:
        return
    if not subscriptions:
        return

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("pywebpush not installed; skipping Web Push")
        return

    payload_obj: dict[str, Any] = {"title": title, "body": body}
    if notification_id is not None:
        payload_obj["notification_id"] = notification_id
    data = json.dumps(payload_obj, ensure_ascii=False)
    vapid_claims = {"sub": mobile_settings.vapid_claim_email}
    vapid_private_key = _normalize_vapid_private_key(mobile_settings.vapid_private_key)
    if not vapid_private_key:
        return

    def _run() -> None:
        for sub_id, endpoint, p256dh, auth in subscriptions:
            try:
                webpush(
                    subscription_info={"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}},
                    data=data,
                    vapid_private_key=vapid_private_key,
                    vapid_claims=vapid_claims,
                    ttl=86400,
                )
            except WebPushException as exc:
                if exc.response is not None and exc.response.status_code in {404, 410}:
                    with SessionLocal() as cleanup:
                        cleanup.execute(delete(WebPushSubscription).where(WebPushSubscription.id == sub_id))
                        cleanup.commit()
                else:
                    logger.debug("Web Push failed for subscription %s: %s", sub_id, exc)

    threading.Thread(target=_run, daemon=True).start()


def send_web_push_to_users_sync(
    *,
    subscriptions: list[tuple[int, str, str, str]],
    title: str,
    body: str,
    notification_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Synchronous sender for diagnostics. Returns per-subscription results.
    """
    results: list[dict[str, Any]] = []
    if not mobile_settings.vapid_public_key or not mobile_settings.vapid_private_key:
        return [{"ok": False, "error": "VAPID keys are not configured"}]
    if not subscriptions:
        return [{"ok": False, "error": "No subscriptions"}]

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        return [{"ok": False, "error": "pywebpush not installed"}]

    payload_obj: dict[str, Any] = {"title": title, "body": body}
    if notification_id is not None:
        payload_obj["notification_id"] = notification_id
    data = json.dumps(payload_obj, ensure_ascii=False)
    vapid_claims = {"sub": mobile_settings.vapid_claim_email}
    vapid_private_key = _normalize_vapid_private_key(mobile_settings.vapid_private_key)
    if not vapid_private_key:
        return [{"ok": False, "error": "Invalid VAPID private key"}]

    # Validate VAPID key is parseable in this runtime.
    try:
        from cryptography.hazmat.primitives import serialization

        serialization.load_pem_private_key(vapid_private_key.encode("utf-8"), password=None)
    except Exception as exc:
        return [{"ok": False, "error": f"Invalid VAPID private key (pem parse): {exc}"}]

    for sub_id, endpoint, p256dh, auth in subscriptions:
        ok_keys, key_err = _validate_subscription_keys(p256dh=p256dh, auth=auth)
        if not ok_keys:
            results.append(
                {
                    "subscription_id": sub_id,
                    "ok": False,
                    "error": key_err,
                }
            )
            continue
        try:
            resp = webpush(
                subscription_info={"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}},
                data=data,
                vapid_private_key=vapid_private_key,
                vapid_claims=vapid_claims,
                ttl=86400,
            )
            status = getattr(resp, "status_code", None)
            results.append({"subscription_id": sub_id, "ok": True, "status_code": status})
        except WebPushException as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            body_text = None
            try:
                body_text = exc.response.text if exc.response is not None else None
            except Exception:
                body_text = None
            if status_code in {404, 410}:
                with SessionLocal() as cleanup:
                    cleanup.execute(delete(WebPushSubscription).where(WebPushSubscription.id == sub_id))
                    cleanup.commit()
            results.append(
                {
                    "subscription_id": sub_id,
                    "ok": False,
                    "status_code": status_code,
                    "error": str(exc),
                    "body": body_text,
                }
            )
        except Exception as exc:
            results.append({"subscription_id": sub_id, "ok": False, "error": str(exc), "exception_type": type(exc).__name__})

    return results


def collect_subscriptions_for_users(db: Session, user_ids: list[int]) -> list[tuple[int, int, str, str, str]]:
    """Returns (subscription_id, user_id, endpoint, p256dh, auth)."""
    if not user_ids:
        return []
    rows = db.scalars(select(WebPushSubscription).where(WebPushSubscription.user_id.in_(user_ids))).all()
    return [(row.id, row.user_id, row.endpoint, row.p256dh, row.auth) for row in rows]
