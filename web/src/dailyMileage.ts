import { parseOdometerKm, parseStageTime } from "./stageDeltas";
import type { DailyMileageDay, PointDto } from "./types";

type StagePoint = Pick<
  PointDto,
  | "departure_time"
  | "time_accepted"
  | "time_departure"
  | "departure_odometer"
  | "registration_time"
  | "time_registration"
  | "registration_odometer"
  | "gate_time"
  | "time_put_on_gate"
  | "gate_odometer"
  | "docs_time"
  | "time_docs"
  | "docs_odometer"
  | "odometer"
>;

type Reading = { day: string; at: number; km: number };

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

function dayFromRaw(raw: string): string | null {
  const dmy = raw.trim().match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})/);
  if (dmy) {
    return `${dmy[3]}-${pad2(Number(dmy[2]))}-${pad2(Number(dmy[1]))}`;
  }
  const parsed = parseStageTime(raw);
  if (!parsed) return null;
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Moscow",
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  }).format(parsed);
}

function stagesOf(point: StagePoint): Array<{ rawTime: string | null | undefined; km: number | null }> {
  return [
    { rawTime: point.departure_time || point.time_accepted || point.time_departure, km: parseOdometerKm(point.departure_odometer) },
    { rawTime: point.registration_time || point.time_registration, km: parseOdometerKm(point.registration_odometer) },
    { rawTime: point.gate_time || point.time_put_on_gate, km: parseOdometerKm(point.gate_odometer) },
    { rawTime: point.docs_time || point.time_docs, km: parseOdometerKm(point.docs_odometer || point.odometer) }
  ];
}

export function formatOdometer(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  if (Math.abs(value - Math.round(value)) < 1e-6) return String(Math.round(value));
  return value.toFixed(1);
}

export function formatDayLabel(dayMsk: string): string {
  const match = dayMsk.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return dayMsk;
  return `${match[3]}.${match[2]}.${match[1]}`;
}

export function suggestDailyMileage(points: StagePoint[] | undefined): DailyMileageDay[] {
  const readings: Reading[] = [];
  for (const point of points || []) {
    for (const stage of stagesOf(point)) {
      if (stage.km == null || !stage.rawTime) continue;
      const day = dayFromRaw(stage.rawTime);
      const at = parseStageTime(stage.rawTime)?.getTime();
      if (!day || at == null) continue;
      readings.push({ day, at, km: stage.km });
    }
  }
  readings.sort((a, b) => a.at - b.at || a.km - b.km);
  if (!readings.length) return [];

  const days: string[] = [];
  for (const item of readings) {
    if (days[days.length - 1] !== item.day) days.push(item.day);
  }

  return days.map((day) => {
    const inDay = readings.filter((item) => item.day === day);
    const before = readings.filter((item) => item.day < day);
    const start = before.length ? before[before.length - 1]!.km : inDay[0]!.km;
    const end = inDay[inDay.length - 1]!.km;
    const km = end >= start ? Math.round(end - start) : null;
    return {
      day_msk: day,
      day_label: formatDayLabel(day),
      suggested_odometer_start: start,
      suggested_odometer_end: end,
      suggested_km: km,
      odometer_start: start,
      odometer_end: end,
      km,
      status: "pending",
      confirmed_at: null,
      edits: []
    };
  });
}

export function dailyMileageDays(route: {
  daily_mileage?: DailyMileageDay[] | null;
  points?: readonly unknown[] | null;
}): DailyMileageDay[] {
  if (route.daily_mileage != null) return route.daily_mileage;
  return suggestDailyMileage((route.points || []) as StagePoint[]);
}

export const DAILY_MILEAGE_STATUS_LABEL: Record<DailyMileageDay["status"], string> = {
  pending: "ожидает подтверждения",
  confirmed: "подтверждено",
  corrected: "изменено водителем"
};
