import type { PointStatus } from "./types";

const STATUS_CHAIN: PointStatus[] = ["new", "process", "registration", "load", "docs", "success"];

const STATUS_LABELS: Record<PointStatus, string> = {
  new: "Новая",
  process: "Выехал",
  registration: "Регистрация",
  load: "На воротах",
  docs: "Документы",
  success: "Выехал с точки"
};

export function nextStatus(current: PointStatus): Exclude<PointStatus, "new"> | null {
  const index = STATUS_CHAIN.indexOf(current);
  if (index < 0 || index + 1 >= STATUS_CHAIN.length) {
    return null;
  }
  return STATUS_CHAIN[index + 1] as Exclude<PointStatus, "new">;
}

export function statusLabel(status: PointStatus): string {
  return STATUS_LABELS[status] ?? status;
}

export function nextStatusLabel(current: PointStatus): string | null {
  const next = nextStatus(current);
  if (!next) {
    return null;
  }
  return statusLabel(next);
}

