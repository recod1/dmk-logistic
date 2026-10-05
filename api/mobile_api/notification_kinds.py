KIND_POINT = "point"
KIND_CHAT = "chat"
KIND_ROUTES = "routes"


def notification_kind(event_type: str) -> str:
    if event_type == "point_status_stale":
        return KIND_POINT
    if event_type == "chat_message":
        return KIND_CHAT
    return KIND_ROUTES


def pref_allows(pref: object | None, kind: str) -> bool:
    if pref is None:
        return True
    if kind == KIND_POINT:
        return not bool(getattr(pref, "mute_point", False))
    if kind == KIND_CHAT:
        return not bool(getattr(pref, "mute_chat", False))
    return not bool(getattr(pref, "mute_routes", False))
