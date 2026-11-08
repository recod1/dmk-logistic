import { plannedDateDisplay, plannedTimeDisplay } from "./plannedTime";

export const LATE_GRACE_MINUTES = 0;
export type LateKind = "" | "risk" | "fact";

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

function plannedWallDate(datePoint?: string | null, pointTime?: string | null): Date | null {
  const date = plannedDateDisplay(datePoint, pointTime);
  const time = plannedTimeDisplay(datePoint, pointTime);
  const dm = /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/.exec(date || "");
  const tm = /^(\d{1,2}):(\d{2})/.exec(time || "");
  if (!dm || !tm) {
    return null;
  }
  const iso = `${dm[3]}-${pad2(Number(dm[2]))}-${pad2(Number(dm[1]))}T${pad2(Number(tm[1]))}:${tm[2]}:00+03:00`;
  const value = new Date(iso);
  return Number.isNaN(value.getTime()) ? null : value;
}

function etaWallDate(datePoint?: string | null, pointTime?: string | null, etaRaw?: string | null): Date | null {
  const eta = (etaRaw || "").trim();
  const isoLocal = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(eta);
  if (isoLocal) {
    const value = new Date(`${isoLocal[1]}-${isoLocal[2]}-${isoLocal[3]}T${isoLocal[4]}:${isoLocal[5]}:00+03:00`);
    return Number.isNaN(value.getTime()) ? null : value;
  }
  const date = plannedDateDisplay(eta) || plannedDateDisplay(datePoint, pointTime);
  const time = plannedTimeDisplay(eta) || plannedTimeDisplay("", eta);
  const dm = /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/.exec(date || "");
  const tm = /^(\d{1,2}):(\d{2})/.exec(time || eta);
  if (!dm || !tm) {
    return null;
  }
  const iso = `${dm[3]}-${pad2(Number(dm[2]))}-${pad2(Number(dm[1]))}T${pad2(Number(tm[1]))}:${tm[2]}:00+03:00`;
  const value = new Date(iso);
  return Number.isNaN(value.getTime()) ? null : value;
}

export function isLaterThanPlan(actual: Date | null, planned: Date | null, graceMinutes = LATE_GRACE_MINUTES): boolean {
  if (!actual || !planned) {
    return false;
  }
  return actual.getTime() > planned.getTime() + Math.max(0, graceMinutes) * 60_000;
}

export function etaIsLate(datePoint?: string | null, pointTime?: string | null, etaRaw?: string | null): boolean {
  const eta = (etaRaw || "").trim();
  if (!eta) {
    return false;
  }
  return isLaterThanPlan(etaWallDate(datePoint, pointTime, eta), plannedWallDate(datePoint, pointTime));
}

export function registrationIsLate(
  occurredAtIso?: string | null,
  datePoint?: string | null,
  pointTime?: string | null
): boolean {
  if (!occurredAtIso) {
    return false;
  }
  const actual = new Date(occurredAtIso);
  if (Number.isNaN(actual.getTime())) {
    return false;
  }
  return isLaterThanPlan(actual, plannedWallDate(datePoint, pointTime));
}

export function pointLateKind(point: {
  date_point?: string | null;
  point_time?: string | null;
  estimated_arrival?: string | null;
  late_kind?: string | null;
  registration_time?: string | null;
  time_registration?: string | null;
}): LateKind {
  const existing = (point.late_kind || "").trim();
  if (existing === "risk" || existing === "fact") {
    return existing;
  }
  const registration = point.registration_time || point.time_registration || null;
  if (registrationIsLate(registration, point.date_point, point.point_time)) {
    return "fact";
  }
  const eta = (point.estimated_arrival || "").trim();
  if (eta && etaIsLate(point.date_point, point.point_time, eta) && !registration) {
    return "risk";
  }
  return "";
}

export function lateKindClass(kind?: string | null): Record<string, boolean> {
  return {
    "late-risk": kind === "risk",
    "late-fact": kind === "fact"
  };
}

const LATE_LINE_RE = /(?=Причина опоздания\s*\([^)]+\):)/;
const LATE_PREFIX_RE = /^Причина опоздания\s*\([^)]+\):\s*/;

export function lateReasonLines(raw?: string | null): string[] {
  const text = (raw || "").trim();
  if (!text) {
    return [];
  }
  const lines: string[] = [];
  for (const chunk of text.split(/\n+/)) {
    const piece = chunk.trim();
    if (!piece) {
      continue;
    }
    const bits = piece.split(LATE_LINE_RE).map((item) => item.trim()).filter(Boolean);
    lines.push(...(bits.length ? bits : [piece]));
  }
  return lines;
}

export function lastLateReasonText(raw?: string | null): string {
  const lines = lateReasonLines(raw);
  if (!lines.length) {
    return "";
  }
  const cleaned = lines[lines.length - 1].replace(LATE_PREFIX_RE, "").trim();
  return cleaned || lines[lines.length - 1];
}

function reasonKey(text: string): string {
  return text.replace(LATE_PREFIX_RE, "").trim().toLowerCase().replace(/\s+/g, " ");
}

/** Одна причина на точку. Две разные — обе, одинаковый текст не повторяется. */
export function uniqueLateReasonLines(raw?: string | null): string[] {
  const seen = new Set<string>();
  const uniqueTexts: string[] = [];
  const labeled: string[] = [];
  for (const line of lateReasonLines(raw)) {
    const text = line.replace(LATE_PREFIX_RE, "").trim();
    const key = reasonKey(text);
    if (!key || seen.has(key)) {
      continue;
    }
    seen.add(key);
    uniqueTexts.push(text);
    labeled.push(LATE_PREFIX_RE.test(line) ? line : `Причина опоздания: ${text}`);
  }
  if (!uniqueTexts.length) {
    return [];
  }
  if (uniqueTexts.length === 1) {
    return [`Причина опоздания: ${uniqueTexts[0]}`];
  }
  return labeled;
}

export function mergeLateReason(existing: string | null | undefined, incoming: string | null | undefined, label: string): string {
  const text = (incoming || "").replace(LATE_PREFIX_RE, "").trim() || lastLateReasonText(existing);
  if (!text) {
    return (existing || "").trim();
  }
  const current = (existing || "").trim();
  const keys = new Set(lateReasonLines(current).map((line) => reasonKey(line)));
  if (keys.has(reasonKey(text))) {
    return current;
  }
  const line = `${label}: ${text}`;
  return current ? `${current}\n${line}` : line;
}
