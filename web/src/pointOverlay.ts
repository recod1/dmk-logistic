import type { PointDto, PointStatus, RouteDto } from "./types";

export type OverlayStageFields = {
  time?: string | null;
  odometer?: string | null;
  time_source?: string | null;
  odometer_source?: string | null;
};

const STATUS_STAGE: Record<
  string,
  {
    time: keyof PointDto;
    legacyTime: keyof PointDto;
    odometer: keyof PointDto;
    timeSource: keyof PointDto;
    odometerSource: keyof PointDto;
  }
> = {
  process: {
    time: "departure_time",
    legacyTime: "time_accepted",
    odometer: "departure_odometer",
    timeSource: "departure_time_source",
    odometerSource: "departure_odometer_source"
  },
  registration: {
    time: "registration_time",
    legacyTime: "time_registration",
    odometer: "registration_odometer",
    timeSource: "registration_time_source",
    odometerSource: "registration_odometer_source"
  },
  load: {
    time: "gate_time",
    legacyTime: "time_put_on_gate",
    odometer: "gate_odometer",
    timeSource: "gate_time_source",
    odometerSource: "gate_odometer_source"
  },
  docs: {
    time: "docs_time",
    legacyTime: "time_docs",
    odometer: "docs_odometer",
    timeSource: "docs_time_source",
    odometerSource: "docs_odometer_source"
  },
  success: {
    time: "docs_time",
    legacyTime: "time_docs",
    odometer: "docs_odometer",
    timeSource: "docs_time_source",
    odometerSource: "docs_odometer_source"
  }
};

export function formatOverlayTime(raw: string | null | undefined): string {
  const text = (raw || "").trim();
  if (!text) return "";
  if (/^\d{2}\.\d{2}\.\d{4}/.test(text)) {
    return text.length >= 16 ? text.slice(0, 16) : text;
  }
  const dt = new Date(text);
  if (Number.isNaN(dt.getTime())) {
    return text;
  }
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(dt.getDate())}.${pad(dt.getMonth() + 1)}.${dt.getFullYear()} ${pad(dt.getHours())}:${pad(dt.getMinutes())}`;
}

export function applyStageOverlayToPoint(point: PointDto, status: PointStatus, fields: OverlayStageFields): PointDto {
  const spec = STATUS_STAGE[status];
  if (!spec) {
    return { ...point, status };
  }
  const time = formatOverlayTime(fields.time);
  const odometer = (fields.odometer || "").trim();
  return {
    ...point,
    status,
    [spec.time]: time || point[spec.time],
    [spec.legacyTime]: time || point[spec.legacyTime],
    [spec.odometer]: odometer || point[spec.odometer],
    [spec.timeSource]: fields.time_source || point[spec.timeSource],
    [spec.odometerSource]: fields.odometer_source || point[spec.odometerSource]
  } as PointDto;
}

export function applyOverlaysToPoints(
  route: RouteDto,
  overlays: Array<{
    point_id: number;
    status: Exclude<PointStatus, "new">;
    occurred_at_client?: string | null;
    time?: string | null;
    odometer?: string | null;
    time_source?: string | null;
    odometer_source?: string | null;
  }>
): PointDto[] {
  const points = Array.isArray(route.points) ? route.points : [];
  if (!overlays.length) {
    return points;
  }
  const byPointId = new Map(overlays.map((item) => [item.point_id, item]));
  return points.map((point) => {
    const overlay = byPointId.get(point.id);
    if (!overlay) {
      return point;
    }
    return applyStageOverlayToPoint(point, overlay.status, {
      time: overlay.time || overlay.occurred_at_client,
      odometer: overlay.odometer,
      time_source: overlay.time_source,
      odometer_source: overlay.odometer_source
    });
  });
}
