const MOSCOW = "Europe/Moscow";
const WALL = /^(\d{2})\.(\d{2})\.(\d{4})(?:[ T](\d{2}):(\d{2}))?/;

/** Настенные часы Москвы для факта этапа (как на сервере). Не использует пояс телефона. */
export function formatInstantMoscow(raw?: string | null): string {
  const text = (raw || "").trim();
  if (!text) {
    return "";
  }
  const wall = WALL.exec(text);
  if (wall && !/[zZ]|[+-]\d{2}:?\d{2}$/.test(text) && !text.includes("T")) {
    const hm = wall[4] && wall[5] ? `${wall[4]}:${wall[5]}` : "";
    return hm ? `${wall[1]}.${wall[2]}.${wall[3]} ${hm}` : `${wall[1]}.${wall[2]}.${wall[3]}`;
  }
  const dt = new Date(text);
  if (Number.isNaN(dt.getTime())) {
    return text;
  }
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-GB", {
      timeZone: MOSCOW,
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23"
    })
      .formatToParts(dt)
      .map((part) => [part.type, part.value])
  );
  return `${parts.day}.${parts.month}.${parts.year} ${parts.hour}:${parts.minute}`;
}

export function moscowClockHm(raw?: string | null): string {
  const full = formatInstantMoscow(raw);
  const match = /(\d{2}:\d{2})$/.exec(full);
  return match ? match[1] : full;
}

export function datetimeLocalKey(value: string): string {
  return (value || "").trim().slice(0, 16);
}

/** Подпись источника, если время не «просто часы Москвы с устройства». */
export function timeSourceCaption(source?: string | null): string {
  if (source === "manual") {
    return "вручную";
  }
  if (source === "wialon") {
    return "Wialon";
  }
  return "";
}

export function factTimesDiffer(left?: string | null, right?: string | null): boolean {
  const a = formatInstantMoscow(left);
  const b = formatInstantMoscow(right);
  return Boolean(a && b && a !== b);
}

export function formatNotificationReceivedAt(iso?: string | null, now = new Date()): string {
  const full = formatInstantMoscow(iso);
  if (!full) {
    return "";
  }
  const nowFull = formatInstantMoscow(now.toISOString());
  const date = full.slice(0, 10);
  const hm = full.slice(11);
  if (date === nowFull.slice(0, 10)) {
    return hm;
  }
  if (full.slice(6, 10) === nowFull.slice(6, 10)) {
    return `${date.slice(0, 5)} ${hm}`;
  }
  return full;
}

export function formatFactPressedCaption(factTime?: string | null, pressedAt?: string | null): string {
  if (!factTimesDiffer(factTime, pressedAt)) {
    return "";
  }
  const hm = moscowClockHm(pressedAt);
  return hm ? `нажато ${hm}` : "";
}
