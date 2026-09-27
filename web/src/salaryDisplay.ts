export function salaryStatusKey(status: string | null | undefined): "confirmed" | "commented" | "archived" | "pending" {
  const t = (status || "").trim();
  if (t === "confirmed") return "confirmed";
  if (t === "commented") return "commented";
  if (t === "archived") return "archived";
  return "pending";
}

export function salaryStatusLabel(status: string | null | undefined): string {
  const key = salaryStatusKey(status);
  if (key === "confirmed") return "Подтверждено";
  if (key === "commented") return "С комментарием";
  if (key === "archived") return "Архив";
  return "Ожидает подтверждения";
}

export function salaryCommentText(comment: string | null | undefined): string {
  const t = (comment || "").trim();
  if (!t || t === "0") return "";
  return t;
}
