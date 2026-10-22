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
  const date = plannedDateDisplay(datePoint, pointTime);
  const eta = (etaRaw || "").trim();
  const dm = /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/.exec(date || "");
  const tm = /^(\d{1,2}):(\d{2})/.exec(eta);
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
