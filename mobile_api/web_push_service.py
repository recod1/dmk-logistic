from __future__ import annotations

import json
import logging
import threading
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from mobile_api.db import SessionLocal
from mobile_api.models import WebPushSubscription
from mobile_api.settings import mobile_settings

logger = logging.getLogger(__name__)


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

    def _run() -> None:
        for sub_id, endpoint, p256dh, auth in subscriptions:
            try:
                webpush(
                    subscription_info={"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}},
                    data=data,
                    vapid_private_key=mobile_settings.vapid_private_key,
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


def collect_subscriptions_for_users(db: Session, user_ids: list[int]) -> list[tuple[int, int, str, str, str]]:
    """Returns (subscription_id, user_id, endpoint, p256dh, auth)."""
    if not user_ids:
        return []
    rows = db.scalars(select(WebPushSubscription).where(WebPushSubscription.user_id.in_(user_ids))).all()
    return [(row.id, row.user_id, row.endpoint, row.p256dh, row.auth) for row in rows]
