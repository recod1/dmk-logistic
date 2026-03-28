function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

/** Значение для input[type=datetime-local] в локальном времени устройства. */
export function toDatetimeLocalValue(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(
    d.getMinutes()
  )}`;
}

/**
 * Парсит значение datetime-local как календарные дату/время в часовом поясе устройства
 * (не как UTC-строку) и возвращает ISO 8601 UTC для API — момент времени совпадает с тем,
 * что водитель видит на часах телефона.
 */
export function fromDatetimeLocalToIso(local: string): string {
  const trimmed = local.trim();
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?/.exec(trimmed);
  if (!match) {
    throw new Error("Некорректная дата и время");
  }
  const y = Number(match[1]);
  const mo = Number(match[2]);
  const d = Number(match[3]);
  const h = Number(match[4]);
  const mi = Number(match[5]);
  const s = match[6] !== undefined ? Number(match[6]) : 0;
  if ([y, mo, d, h, mi, s].some((n) => Number.isNaN(n))) {
    throw new Error("Некорректная дата и время");
  }
  const deviceLocal = new Date(y, mo - 1, d, h, mi, s);
  if (Number.isNaN(deviceLocal.getTime())) {
    throw new Error("Некорректная дата и время");
  }
  return deviceLocal.toISOString();
}
