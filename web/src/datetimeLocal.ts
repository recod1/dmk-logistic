function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

/** Значение для input[type=datetime-local] в локальном времени устройства. */
export function toDatetimeLocalValue(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(
    d.getMinutes()
  )}`;
}

/** Парсит datetime-local как локальное время и возвращает ISO UTC для API. */
export function fromDatetimeLocalToIso(local: string): string {
  const d = new Date(local);
  if (Number.isNaN(d.getTime())) {
    throw new Error("Некорректная дата и время");
  }
  return d.toISOString();
}
