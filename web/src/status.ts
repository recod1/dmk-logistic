import type { PointStatus } from "./types";

const STATUS_CHAIN: PointStatus[] = ["new", "process", "registration", "load", "docs"];

const STATUS_LABELS: Record<PointStatus, string> = {
  new: "Новая",
  process: "Выехал на точку",
  registration: "Зарегистрировался",
  load: "На воротах",
  docs: "Забрал документы",
  success: "Забрал документы"
};

export function isPointDone(status: PointStatus): boolean {
  return status === "docs" || status === "success";
}

export function nextStatus(current: PointStatus): Exclude<PointStatus, "new"> | null {
  if (isPointDone(current)) {
    return null;
  }
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

