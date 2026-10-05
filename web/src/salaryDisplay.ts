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

export type SalaryListTab = "all" | "pending" | "commented" | "confirmed";

export function salaryMatchesTab(status: string | null | undefined, tab: SalaryListTab): boolean {
  if (tab === "all") return true;
  return salaryStatusKey(status) === tab;
}

function salaryChronoKey(row: { id: number; date_salary?: string | null }): [number, number] {
  const match = /^(\d{1,2})[./](\d{1,2})[./](\d{2,4})/.exec((row.date_salary || "").trim());
  if (!match) {
    return [0, row.id];
  }
  let year = Number(match[3]);
  if (year < 100) year += 2000;
  return [year * 10000 + Number(match[2]) * 100 + Number(match[1]), row.id];
}

export function compareSalaryChronoDesc(
  a: { id: number; date_salary?: string | null },
  b: { id: number; date_salary?: string | null }
): number {
  const ka = salaryChronoKey(a);
  const kb = salaryChronoKey(b);
  if (kb[0] !== ka[0]) return kb[0] - ka[0];
  return kb[1] - ka[1];
}

export function sortSalaryChronoDesc<T extends { id: number; date_salary?: string | null }>(items: T[]): T[] {
  return [...items].sort(compareSalaryChronoDesc);
}
