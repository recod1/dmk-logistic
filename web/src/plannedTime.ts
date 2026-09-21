const DATE_ISO = /(\d{4})-(\d{2})-(\d{2})/;
const DATE_DMY = /(\d{1,2})[./](\d{1,2})[./](\d{2,4})/;
const TIME = /(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\s*([AaPp][Mm]))?/;

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

function hourFromToken(hour: number, ampm?: string | null): number {
  if (!ampm) {
    return hour;
  }
  const suffix = ampm.toUpperCase();
  if (suffix === "AM") {
    return hour === 12 ? 0 : hour;
  }
  if (suffix === "PM") {
    return hour === 12 ? 12 : hour + 12;
  }
  return hour;
}

export function splitPlannedDateTime(raw?: string | null): { date: string; time: string } {
  const text = (raw || "").trim();
  if (!text) {
    return { date: "", time: "" };
  }
  let date = "";
  let rest = text;
  const iso = DATE_ISO.exec(text);
  const dmy = DATE_DMY.exec(text);
  const isoAt = iso?.index ?? -1;
  const dmyAt = dmy?.index ?? -1;
  if (iso && (dmyAt < 0 || isoAt <= dmyAt)) {
    const year = Number(iso[1]);
    const month = Number(iso[2]);
    const day = Number(iso[3]);
    if (month >= 1 && month <= 12 && day >= 1 && day <= 31) {
      date = `${pad2(day)}.${pad2(month)}.${year}`;
    }
    rest = `${text.slice(0, iso.index)} ${text.slice(iso.index + iso[0].length)}`.trim();
  } else if (dmy) {
    const day = Number(dmy[1]);
    const month = Number(dmy[2]);
    let year = Number(dmy[3]);
    if (year < 100) {
      year += 2000;
    }
    if (month >= 1 && month <= 12 && day >= 1 && day <= 31) {
      date = `${pad2(day)}.${pad2(month)}.${year}`;
    }
    rest = `${text.slice(0, dmy.index)} ${text.slice(dmy.index + dmy[0].length)}`.trim();
  }
  const search = rest || text;
  const tm = TIME.exec(search);
  let time = "";
  if (tm) {
    const hour = hourFromToken(Number(tm[1]), tm[4]);
    const minute = Number(tm[2]);
    if (hour >= 0 && hour <= 23 && minute >= 0 && minute <= 59) {
      time = `${pad2(hour)}:${pad2(minute)}`;
    }
  }
  return { date, time };
}

export function plannedDateInputValue(date?: string | null, time?: string | null): string {
  const split = splitPlannedDateTime([date, time].filter(Boolean).join(" "));
  const source = split.date || (date || "").trim();
  const parsed = splitPlannedDateTime(source);
  const dmy = DATE_DMY.exec(parsed.date || source);
  if (!dmy) {
    const iso = DATE_ISO.exec(source);
    return iso ? `${iso[1]}-${iso[2]}-${iso[3]}` : "";
  }
  let year = Number(dmy[3]);
  if (year < 100) {
    year += 2000;
  }
  return `${year}-${pad2(Number(dmy[2]))}-${pad2(Number(dmy[1]))}`;
}

export function plannedTimeInputValue(date?: string | null, time?: string | null): string {
  const fromTime = splitPlannedDateTime(time || "").time;
  if (fromTime) {
    return fromTime;
  }
  return splitPlannedDateTime(date || "").time;
}

export function plannedDateDisplay(date?: string | null, time?: string | null): string {
  const splitFromDate = splitPlannedDateTime(date || "");
  if (splitFromDate.date) {
    return splitFromDate.date;
  }
  return splitPlannedDateTime(time || "").date;
}

export function plannedTimeDisplay(date?: string | null, time?: string | null): string {
  const fromTime = splitPlannedDateTime(time || "").time;
  if (fromTime) {
    return fromTime;
  }
  return splitPlannedDateTime(date || "").time;
}

export function plannedScheduleDisplay(date?: string | null, time?: string | null): string {
  return [plannedDateDisplay(date, time), plannedTimeDisplay(date, time)].filter(Boolean).join(" ");
}
