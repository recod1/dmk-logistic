import { formatDuration, parseOdometerKm, parseStageTime } from "./stageDeltas";

export type RouteAnalyticsPoint = {
  type_point?: string | null;
  departure_time?: string | null;
  time_accepted?: string | null;
  time_departure?: string | null;
  departure_odometer?: string | null;
  registration_time?: string | null;
  time_registration?: string | null;
  registration_odometer?: string | null;
  gate_time?: string | null;
  time_put_on_gate?: string | null;
  gate_odometer?: string | null;
  docs_time?: string | null;
  time_docs?: string | null;
  docs_odometer?: string | null;
  odometer?: string | null;
};

export type RouteAnalyticsPayload = {
  total_minutes?: number | null;
  total_km?: number | null;
  work_minutes?: number | null;
  work_km?: number | null;
};

export type RouteAnalyticsView = {
  totalTime: string;
  totalKm: string;
  workTime: string;
  workKm: string;
};

type Stage = { time: Date | null; km: number | null };

const EMPTY = "нет данных";

function stagesOf(point: RouteAnalyticsPoint): Stage[] {
  return [
    {
      time: parseStageTime(point.departure_time || point.time_accepted || point.time_departure),
      km: parseOdometerKm(point.departure_odometer)
    },
    {
      time: parseStageTime(point.registration_time || point.time_registration),
      km: parseOdometerKm(point.registration_odometer)
    },
    {
      time: parseStageTime(point.gate_time || point.time_put_on_gate),
      km: parseOdometerKm(point.gate_odometer)
    },
    {
      time: parseStageTime(point.docs_time || point.time_docs),
      km: parseOdometerKm(point.docs_odometer || point.odometer)
    }
  ];
}

function firstFilled(point: RouteAnalyticsPoint | undefined): Stage {
  if (!point) return { time: null, km: null };
  return stagesOf(point).find((row) => row.time || row.km != null) || { time: null, km: null };
}

function lastFilled(point: RouteAnalyticsPoint | undefined): Stage {
  if (!point) return { time: null, km: null };
  return [...stagesOf(point)].reverse().find((row) => row.time || row.km != null) || { time: null, km: null };
}

function registrationOf(point: RouteAnalyticsPoint | undefined): Stage {
  if (!point) return { time: null, km: null };
  return stagesOf(point)[1]!;
}

function docsOf(point: RouteAnalyticsPoint | undefined): Stage {
  if (!point) return { time: null, km: null };
  return stagesOf(point)[3]!;
}

function spanTime(start: Stage, end: Stage): string {
  if (!start.time || !end.time) return EMPTY;
  const minutes = (end.time.getTime() - start.time.getTime()) / 60000;
  return formatDuration(minutes) || EMPTY;
}

function spanKm(start: Stage, end: Stage): string {
  if (start.km == null || end.km == null) return EMPTY;
  const km = Math.round(end.km - start.km);
  if (!Number.isFinite(km)) return EMPTY;
  return km < 0 ? "—" : `${km} км`;
}

function fromPayload(payload: RouteAnalyticsPayload): RouteAnalyticsView {
  return {
    totalTime: payload.total_minutes != null ? formatDuration(payload.total_minutes) || EMPTY : EMPTY,
    totalKm: payload.total_km != null ? `${payload.total_km} км` : EMPTY,
    workTime: payload.work_minutes != null ? formatDuration(payload.work_minutes) || EMPTY : EMPTY,
    workKm: payload.work_km != null ? `${payload.work_km} км` : EMPTY
  };
}

function fromPoints(points: RouteAnalyticsPoint[] | null | undefined): RouteAnalyticsView {
  const list = Array.isArray(points) ? points : [];
  const first = list[0];
  const last = list[list.length - 1];
  let end = lastFilled(last);
  if (!end.time && end.km == null) {
    for (let i = list.length - 1; i >= 0; i -= 1) {
      const candidate = lastFilled(list[i]);
      if (candidate.time || candidate.km != null) {
        end = candidate;
        break;
      }
    }
  }
  const start = firstFilled(first);
  const workStart = registrationOf(first);
  const workEnd = docsOf(last);
  return {
    totalTime: spanTime(start, end),
    totalKm: spanKm(start, end),
    workTime: spanTime(workStart, workEnd),
    workKm: spanKm(workStart, workEnd)
  };
}

function prefer(server: string, local: string): string {
  return server !== EMPTY ? server : local;
}

export function routeAnalyticsView(
  points: RouteAnalyticsPoint[] | null | undefined,
  payload?: RouteAnalyticsPayload | null
): RouteAnalyticsView {
  const local = fromPoints(points);
  if (!payload) {
    return local;
  }
  const server = fromPayload(payload);
  return {
    totalTime: prefer(server.totalTime, local.totalTime),
    totalKm: prefer(server.totalKm, local.totalKm),
    workTime: prefer(server.workTime, local.workTime),
    workKm: prefer(server.workKm, local.workKm)
  };
}
