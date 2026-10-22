const DATE_ISO = /(\d{4})-(\d{2})-(\d{2})/;
const DATE_DMY = /(\d{1,2})[./](\d{1,2})[./](\d{2,4})/;
const TIME = /(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\s*([AaPp][Mm])(?![A-Za-z]))?/;
const TIME_FLEX = /(\d{1,2})[.\-](\d{2})(?:[.\-](\d{2}))?/;
const MS_DATE = /\/Date\((-?\d+)(?:[+-]\d{4})?\)\//;

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

function hourFromToken(hour: number, ampm?: string | null): number {
  if (!ampm || hour > 12) {
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
  const msDate = MS_DATE.exec(text);
  if (msDate && !text.includes(":") && !/\d{4}-\d{2}-\d{2}/.test(text)) {
    const moscow = new Date(Number(msDate[1]) + 3 * 60 * 60 * 1000);
    return {
      date: `${pad2(moscow.getUTCDate())}.${pad2(moscow.getUTCMonth() + 1)}.${moscow.getUTCFullYear()}`,
      time: `${pad2(moscow.getUTCHours())}:${pad2(moscow.getUTCMinutes())}`
    };
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
  const search = date ? rest : text;
  return { date, time: pickWallClockTime(search) };
}

function isDateFragment(text: string, start: number, end: number): boolean {
  const rest = text.slice(end);
  if (/^[./-]\d{2,4}(?!\d)/.test(rest)) {
    return true;
  }
  return /\d{4}[./-]$/.test(text.slice(0, start));
}

function pickWallClockTime(search: string): string {
  const candidates: Array<{ hour: number; minute: number; afternoon: boolean }> = [];
  const timeRe = new RegExp(TIME.source, "g");
  let tm: RegExpExecArray | null;
  while ((tm = timeRe.exec(search))) {
    const hour = hourFromToken(Number(tm[1]), tm[4]);
    const minute = Number(tm[2]);
    if (hour >= 0 && hour <= 23 && minute >= 0 && minute <= 59) {
      candidates.push({ hour, minute, afternoon: hour >= 13 || Boolean(tm[4]) });
    }
  }
  if (!candidates.length) {
    const flexRe = new RegExp(TIME_FLEX.source, "g");
    let flex: RegExpExecArray | null;
    while ((flex = flexRe.exec(search))) {
      if (flex[3] && /^\d/.test(search.slice(flex.index + flex[0].length))) {
        continue;
      }
      if (isDateFragment(search, flex.index, flex.index + flex[0].length)) {
        continue;
      }
      const hour = Number(flex[1]);
      const minute = Number(flex[2]);
      if (hour >= 0 && hour <= 23 && minute >= 0 && minute <= 59) {
        candidates.push({ hour, minute, afternoon: hour >= 13 });
      }
    }
  }
  if (!candidates.length) {
    return "";
  }
  const afternoon = candidates.find((item) => item.hour >= 13);
  const chosen = afternoon || candidates[0];
  return `${pad2(chosen.hour)}:${pad2(chosen.minute)}`;
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
  return plannedTimeDisplay(date, time);
}

export function plannedDateDisplay(date?: string | null, time?: string | null): string {
  const splitFromDate = splitPlannedDateTime(date || "");
  if (splitFromDate.date) {
    return splitFromDate.date;
  }
  return splitPlannedDateTime(time || "").date;
}

function clockHm(value: string): { hour: number; minute: number } | null {
  const match = /^(\d{1,2}):(\d{2})/.exec((value || "").trim());
  if (!match) {
    return null;
  }
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) {
    return null;
  }
  return { hour, minute };
}

/** If 1C sent 14:00 on the date and 02:00 in a 12-hour time field, keep 14:00. */
export function prefer24hWallTime(timeFromDate: string, timeFromTime: string): string {
  if (timeFromDate && timeFromTime) {
    const left = clockHm(timeFromDate);
    const right = clockHm(timeFromTime);
    if (left && right && left.minute === right.minute && Math.abs(left.hour - right.hour) === 12) {
      const hour = Math.max(left.hour, right.hour);
      return `${pad2(hour)}:${pad2(left.minute)}`;
    }
    if (left && right && left.hour >= 13 && right.hour <= 12) {
      return timeFromDate;
    }
    return timeFromTime;
  }
  return timeFromTime || timeFromDate;
}

export function plannedTimeDisplay(date?: string | null, time?: string | null): string {
  const fromTime = splitPlannedDateTime(time || "").time;
  const fromDate = splitPlannedDateTime(date || "").time;
  return prefer24hWallTime(fromDate, fromTime);
}

export function plannedScheduleDisplay(date?: string | null, time?: string | null): string {
  return [plannedDateDisplay(date, time), plannedTimeDisplay(date, time)].filter(Boolean).join(" ");
}

export function normalizePlannedTimeInput(raw: string): string {
  const trimmed = (raw || "").trim();
  return splitPlannedDateTime(trimmed).time || trimmed;
}
