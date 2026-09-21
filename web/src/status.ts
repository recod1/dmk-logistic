import { plannedDateDisplay, plannedTimeDisplay } from "./plannedTime";
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

const LIST_POINT_STATUS_LABELS: Record<string, string> = {
  new: "Новая",
  process: "Выехал",
  registration: "Зарегистрировался",
  load: "На воротах",
  docs: "Забрал документы",
  success: "Забрал документы"
};

export function statusLabel(status: PointStatus): string {
  return STATUS_LABELS[status] ?? status;
}

export function listPointStatusLabel(status: string | null | undefined): string {
  if (!status) {
    return "";
  }
  return LIST_POINT_STATUS_LABELS[status] ?? status;
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
  if (typeof navigator !== "undefined") {
    const ua = navigator.userAgent || "";
    const isiOS =
      /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    if (isiOS) {
      return `https://maps.apple.com/?q=${q}`;
    }
  }
  return `geo:0,0?q=${q}`;
}

export function mapsLinkTarget(): "_self" | "_blank" {
  if (typeof navigator === "undefined") {
    return "_blank";
  }
  const ua = navigator.userAgent || "";
  const isiOS =
    /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  return isiOS ? "_self" : "_blank";
}

export function pointTypeLabel(type: string | null | undefined): string {
  if (type === "unloading") return "Выгрузка";
  if (type === "loading") return "Загрузка";
  return "";
}

export function formatPointSchedule(
  type?: string | null,
  date?: string | null,
  time?: string | null
): string {
  const kind = pointTypeLabel(type);
  const when = [plannedDateDisplay(date, time), plannedTimeDisplay(date, time)].filter(Boolean).join(" ");
  if (kind && when) {
    return `${kind}: ${when}`;
  }
  return when || kind;
}

export function formatListStatusWithFact(statusLabelText: string, factTime?: string | null): string {
  const fact = (factTime || "").trim();
  if (!statusLabelText) {
    return fact;
  }
  return fact ? `${statusLabelText} · ${fact}` : statusLabelText;
}

