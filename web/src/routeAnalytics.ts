import { formatStageDelta, parseOdometerKm, type StageDeltaInput } from "./stageDeltas";

export type RouteAnalyticsPoint = {
  type_point?: string | null;
  departure_time?: string | null;
  time_accepted?: string | null;
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
};

export type RouteAnalytics = {
  total: string | null;
  work: string | null;
};

function firstFilled(point: RouteAnalyticsPoint): StageDeltaInput {
  const rows: StageDeltaInput[] = [
    { time: point.departure_time || point.time_accepted, odometer: point.departure_odometer },
    { time: point.registration_time || point.time_registration, odometer: point.registration_odometer },
    { time: point.gate_time || point.time_put_on_gate, odometer: point.gate_odometer },
    { time: point.docs_time || point.time_docs, odometer: point.docs_odometer }
  ];
  return rows.find((row) => Boolean((row.time || "").trim() || (row.odometer || "").trim())) || {};
}

function docsStage(point: RouteAnalyticsPoint): StageDeltaInput {
  return { time: point.docs_time || point.time_docs, odometer: point.docs_odometer };
}

function registrationStage(point: RouteAnalyticsPoint): StageDeltaInput {
  return { time: point.registration_time || point.time_registration, odometer: point.registration_odometer };
}

function lastFilled(point: RouteAnalyticsPoint): StageDeltaInput {
  const rows: StageDeltaInput[] = [
    { time: point.docs_time || point.time_docs, odometer: point.docs_odometer },
    { time: point.gate_time || point.time_put_on_gate, odometer: point.gate_odometer },
    { time: point.registration_time || point.time_registration, odometer: point.registration_odometer },
    { time: point.departure_time || point.time_accepted, odometer: point.departure_odometer }
  ];
  return rows.find((row) => Boolean((row.time || "").trim() || (row.odometer || "").trim())) || {};
}

export function routeAnalyticsForPoints(points: RouteAnalyticsPoint[] | null | undefined): RouteAnalytics {
  const list = Array.isArray(points) ? points : [];
  if (!list.length) {
    return { total: null, work: null };
  }
  const first = list[0]!;
  const last = list[list.length - 1]!;
  const firstLoading = list.find((point) => (point.type_point || "").trim() === "loading") || first;
  const total = formatStageDelta(firstFilled(first), lastFilled(last), "начало рейса", "конец рейса");
  const work = formatStageDelta(
    registrationStage(firstLoading),
    docsStage(last),
    "регистрация на первой загрузке",
    "документы на последней точке"
  );
  return { total, work };
}

export function routeMileageKm(points: RouteAnalyticsPoint[] | null | undefined): number | null {
  const list = Array.isArray(points) ? points : [];
  if (!list.length) return null;
  const start = parseOdometerKm(firstFilled(list[0]!).odometer);
  const end = parseOdometerKm(lastFilled(list[list.length - 1]!).odometer);
  if (start == null || end == null) return null;
  const km = Math.round(end - start);
  return Number.isFinite(km) ? km : null;
}
