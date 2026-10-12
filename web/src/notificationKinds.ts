export type NotificationKind = "point" | "chat" | "routes" | "salary";

export const NOTIFICATION_KIND_TABS: NotificationKind[] = ["point", "chat", "routes", "salary"];

export function visibleNotificationKindTabs(showSalary: boolean): NotificationKind[] {
  if (showSalary) {
    return NOTIFICATION_KIND_TABS;
  }
  return NOTIFICATION_KIND_TABS.filter((kind) => kind !== "salary");
}

export function notificationKind(eventType: string): NotificationKind {
  if (eventType === "point_status_stale") {
    return "point";
  }
  if (eventType === "chat_message") {
    return "chat";
  }
  if (eventType === "salary_new" || eventType === "salary_confirmed" || eventType === "salary_commented") {
    return "salary";
  }
  return "routes";
}

export const NOTIFICATION_KIND_LABELS: Record<NotificationKind, string> = {
  point: "Ожидание на точке",
  chat: "Чаты",
  routes: "Рейсы",
  salary: "Расчеты"
};
