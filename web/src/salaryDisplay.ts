export function salaryStatusKey(status: string | null | undefined): "confirmed" | "commented" | "pending" {
  const t = (status || "").trim();
  if (t === "confirmed") return "confirmed";
  if (t === "commented") return "commented";
  return "pending";
}

export function salaryStatusLabel(status: string | null | undefined): string {
  const key = salaryStatusKey(status);
  if (key === "confirmed") return "Подтверждено";
  if (key === "commented") return "С комментарием";
  return "Ожидает подтверждения";
}

export function salaryCommentText(comment: string | null | undefined): string {
  const t = (comment || "").trim();
  if (!t || t === "0") return "";
  return t;
}
