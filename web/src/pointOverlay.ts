import { formatInstantMoscow } from "./factTime";
import type { PointDto, PointStatus, RouteDto } from "./types";

export type OverlayStageFields = {
  time?: string | null;
  pressed_at?: string | null;
  odometer?: string | null;
  time_source?: string | null;
  odometer_source?: string | null;
  estimated_arrival?: string | null;
};

const STATUS_STAGE: Record<
  string,
  {
    time: keyof PointDto;
    legacyTime: keyof PointDto;
    pressedAt: keyof PointDto;
    odometer: keyof PointDto;
    timeSource: keyof PointDto;
    odometerSource: keyof PointDto;
  }
> = {
  process: {
    time: "departure_time",
    legacyTime: "time_accepted",
    pressedAt: "departure_pressed_at",
    odometer: "departure_odometer",
    timeSource: "departure_time_source",
    odometerSource: "departure_odometer_source"
  },
  registration: {
    time: "registration_time",
    legacyTime: "time_registration",
    pressedAt: "registration_pressed_at",
    odometer: "registration_odometer",
    timeSource: "registration_time_source",
    odometerSource: "registration_odometer_source"
  },
  load: {
    time: "gate_time",
    legacyTime: "time_put_on_gate",
    pressedAt: "gate_pressed_at",
    odometer: "gate_odometer",
    timeSource: "gate_time_source",
    odometerSource: "gate_odometer_source"
  },
  docs: {
    time: "docs_time",
    legacyTime: "time_docs",
    pressedAt: "docs_pressed_at",
    odometer: "docs_odometer",
    timeSource: "docs_time_source",
    odometerSource: "docs_odometer_source"
  },
  success: {
    time: "docs_time",
    legacyTime: "time_docs",
    pressedAt: "docs_pressed_at",
    odometer: "docs_odometer",
    timeSource: "docs_time_source",
    odometerSource: "docs_odometer_source"
  }
};

export function formatOverlayTime(raw: string | null | undefined): string {
  return formatInstantMoscow(raw);
}

export function rollbackStageOnPoint(
  point: PointDto,
  rejectedStatus: string,
  previousStatus: PointStatus
): PointDto {
  const spec = STATUS_STAGE[rejectedStatus];
  const cleared = spec
    ? {
        [spec.time]: null,
        [spec.legacyTime]: null,
        [spec.pressedAt]: null,
        [spec.odometer]: null,
        [spec.timeSource]: null,
        [spec.odometerSource]: null
      }
    : {};
  return {
    ...point,
    ...cleared,
    status: previousStatus,
    estimated_arrival: rejectedStatus === "process" ? "" : point.estimated_arrival
  } as PointDto;
}

export function applyStageOverlayToPoint(point: PointDto, status: PointStatus, fields: OverlayStageFields): PointDto {
  const spec = STATUS_STAGE[status];
  if (!spec) {
    return { ...point, status };
  }
  const time = formatOverlayTime(fields.time);
  const pressed = formatOverlayTime(fields.pressed_at);
  const odometer = (fields.odometer || "").trim();
  const eta = (fields.estimated_arrival || "").trim();
  return {
    ...point,
    status,
    estimated_arrival: eta || point.estimated_arrival || "",
    [spec.time]: time || point[spec.time],
    [spec.legacyTime]: time || point[spec.legacyTime],
    [spec.pressedAt]: pressed && pressed !== time ? pressed : null,
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
    pressed_at?: string | null;
    odometer?: string | null;
    time_source?: string | null;
    odometer_source?: string | null;
    estimated_arrival?: string | null;
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
      pressed_at: overlay.pressed_at,
      odometer: overlay.odometer,
      time_source: overlay.time_source,
      odometer_source: overlay.odometer_source,
      estimated_arrival: overlay.estimated_arrival
    });
  });
}
