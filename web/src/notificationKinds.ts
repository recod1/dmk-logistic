export type NotificationKind = "point" | "chat" | "routes";

export function notificationKind(eventType: string): NotificationKind {
  if (eventType === "point_status_stale") {
    return "point";
  }
  if (eventType === "chat_message") {
    return "chat";
  }
  return "routes";
}

export const NOTIFICATION_KIND_LABELS: Record<NotificationKind, string> = {
  point: "Ожидание на точке",
  chat: "Чаты",
  routes: "Рейсы"
};
