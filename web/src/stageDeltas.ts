export type StageDeltaInput = {
  time?: string | null;
  odometer?: string | null;
};

const STAGE_ORDER = ["departure", "registration", "gate", "docs"] as const;

function parseStageTime(raw: string | null | undefined): Date | null {
  const text = (raw || "").trim();
  if (!text) return null;
  const dmy = text.match(/^(\d{2})\.(\d{2})\.(\d{4})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?/);
  if (dmy) {
    const [, dd, mm, yyyy, hh = "0", mi = "0", ss = "0"] = dmy;
    const dt = new Date(Number(yyyy), Number(mm) - 1, Number(dd), Number(hh), Number(mi), Number(ss));
    return Number.isNaN(dt.getTime()) ? null : dt;
  }
  const iso = new Date(text);
  return Number.isNaN(iso.getTime()) ? null : iso;
}

export function parseOdometerKm(raw: string | null | undefined): number | null {
  const text = (raw || "").trim();
  if (!text) return null;
  const match = text.replace(/\s+/g, " ").match(/(-?\d+(?:[.,]\d+)?)/);
  if (!match) return null;
  const value = Number(match[1].replace(",", "."));
  return Number.isFinite(value) ? value : null;
}

function formatMinutes(deltaMin: number): string {
  const abs = Math.abs(Math.round(deltaMin));
  const hours = Math.floor(abs / 60);
  const minutes = abs % 60;
  if (hours && minutes) return `${hours} ч ${minutes} мин`;
  if (hours) return `${hours} ч`;
  return `${minutes} мин`;
}

export function formatStageDelta(prev: StageDeltaInput, next: StageDeltaInput): string | null {
  const prevTime = parseStageTime(prev.time);
  const nextTime = parseStageTime(next.time);
  const prevKm = parseOdometerKm(prev.odometer);
  const nextKm = parseOdometerKm(next.odometer);
  const parts: string[] = [];
  if (prevTime && nextTime) {
    const minutes = (nextTime.getTime() - prevTime.getTime()) / 60000;
    if (Number.isFinite(minutes)) {
      const sign = minutes < 0 ? "−" : "+";
      parts.push(`${sign}${formatMinutes(minutes)}`);
    }
  }
  if (prevKm != null && nextKm != null) {
    const km = Math.round(nextKm - prevKm);
    parts.push(km < 0 ? "—" : `+${km} км`);
  }
  return parts.length ? parts.join(" · ") : null;
}

export function stageDeltasForPoint(point: {
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
}): Partial<Record<(typeof STAGE_ORDER)[number], string>> {
  const rows: Array<{ key: (typeof STAGE_ORDER)[number]; time?: string | null; odometer?: string | null }> = [
    { key: "departure", time: point.departure_time || point.time_accepted, odometer: point.departure_odometer },
    { key: "registration", time: point.registration_time || point.time_registration, odometer: point.registration_odometer },
    { key: "gate", time: point.gate_time || point.time_put_on_gate, odometer: point.gate_odometer },
    { key: "docs", time: point.docs_time || point.time_docs, odometer: point.docs_odometer }
  ];
  const out: Partial<Record<(typeof STAGE_ORDER)[number], string>> = {};
  let prev: StageDeltaInput | null = null;
  for (const row of rows) {
    const filled = Boolean((row.time || "").trim() || (row.odometer || "").trim());
    if (filled && prev) {
      const label = formatStageDelta(prev, row);
      if (label) out[row.key] = label;
    }
    if (filled) prev = row;
  }
  return out;
}
