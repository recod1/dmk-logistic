import type { PointStatus } from "./types";

const STATUS_CHAIN: PointStatus[] = ["new", "process", "registration", "load", "docs"];

export const ROUTE_STATUS_LABELS: Record<string, string> = {
  new: "Не принят",
  process: "В процессе",
  success: "Завершён",
  cancelled: "Отменён"
};

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

export function routeStatusLabel(status: string): string {
  return ROUTE_STATUS_LABELS[status] ?? status;
}

export function previousStatus(current: PointStatus): PointStatus | null {
  if (current === "success") {
    return "load";
  }
  const index = STATUS_CHAIN.indexOf(current);
  if (index <= 0) {
    return null;
  }
  return STATUS_CHAIN[index - 1]!;
}

export function canRevertPointStatus(status: PointStatus): boolean {
  return previousStatus(status) !== null;
}

export function mapsSearchUrl(address: string): string {
  const trimmed = address.trim();
  const q = encodeURIComponent(trimmed);
  // geo: opens a "choose maps app" dialog on most Android devices (instead of forcing Google Maps).
  // Use query form to allow geocoding by address.
  return `geo:0,0?q=${q}`;
}

