export type ShiftWorkflow = "draft" | "active" | "closing" | "closed";
export type ShiftPhase = "start" | "end";
export type CheckState = "ok" | "bad" | null;
export type DocHas = "y" | "n" | "x" | null;

export interface PhotoSlotDef {
  k: string;
  n: string;
  req?: boolean;
}

export interface ShiftDamage {
  id: string;
  note: string;
}

export interface ShiftCheck {
  id: string;
  name: string;
  st: CheckState;
  note: string;
}

export interface ShiftDoc {
  id: string;
  name: string;
  needs_exp: boolean;
  has: DocHas;
  exp: string;
  kind: string;
  d1: string;
  d2: string;
  custom: boolean;
}

export interface ShiftPhasePayload {
  time: string;
  place: string;
  odo: string;
  fuel: string;
  reefer: string;
  temp: string;
  signed_at?: string | null;
  damages: ShiftDamage[];
  checks: ShiftCheck[];
  docs: ShiftDoc[];
  photos_meta?: Record<string, { q?: string[] }>;
}

export interface ShiftRefuel {
  id: string;
  time: string;
  liters: string;
  odo: string;
  place: string;
}

export const TRUCK_SLOTS: PhotoSlotDef[] = [
  { k: "fl", n: "Спереди слева" },
  { k: "front", n: "Спереди", req: true },
  { k: "fr", n: "Спереди справа" },
  { k: "left", n: "Левый борт", req: true },
  { k: "right", n: "Правый борт", req: true },
  { k: "rl", n: "Сзади слева" },
  { k: "rear", n: "Сзади", req: true },
  { k: "rr", n: "Сзади справа" }
];

export const CAB_SLOTS: PhotoSlotDef[] = [
  { k: "cab", n: "Место водителя", req: true },
  { k: "sleeper", n: "Спальник и салон", req: true }
];

export const METER_SLOTS: PhotoSlotDef[] = [
  { k: "odo", n: "Одометр", req: true },
  { k: "fuel", n: "Уровень топлива", req: true },
  { k: "reefer", n: "Моточасы рефа", req: true }
];

export const ALL_SLOTS: PhotoSlotDef[] = [...TRUCK_SLOTS, ...CAB_SLOTS, ...METER_SLOTS];
export const STEPS = ["Данные", "Фото ТС", "Проверка", "Итог"] as const;
export const PHASE_NAME: Record<ShiftPhase, string> = { start: "Приёмка", end: "Сдача" };
export const WARN_DAYS = 30;
export const KIND_META: Record<string, { l1: string; l2: string; p1: number; p2: number; n1: string; n2: string }> = {
  med: { l1: "Дата прохождения врачей", l2: "Дата аттестации", p1: 12, p2: 24, n1: "Осмотр врачей", n2: "Аттестация" },
  san: { l1: "Дата оформления", l2: "Дата санобработки", p1: 12, p2: 1, n1: "Санпаспорт", n2: "Санобработка" }
};

const CHECKS = [
  "Шины и колёса",
  "Световые приборы и сигналы",
  "Течи масла, топлива, ОЖ",
  "Тормоза и пневмосистема",
  "Седельно-сцепное устройство",
  "Тахограф исправен",
  "Рефрижератор работает",
  "Огнетушитель",
  "Аптечка",
  "Знак аварийной остановки",
  "Противооткатные упоры",
  "Светоотражающий жилет",
  "Пломба и запоры прицепа"
];

export function uid(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

export function fmtDT(value?: string | number | null): string {
  if (!value && value !== 0) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function fmtD(iso?: string | null): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  if (!y || !m || !d) return iso;
  return `${d}.${m}.${y}`;
}

export function fmtNum(value: string | number | null | undefined): string {
  if (value === "" || value == null || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString("ru-RU");
}

const DEFAULT_DOCS: Array<[string, boolean, string]> = [
  ["Водительское удостоверение", true, ""],
  ["Карта водителя (тахограф)", true, ""],
  ["Медицинская справка", true, ""],
  ["СТС тягача", false, ""],
  ["СТС прицепа", false, ""],
  ["Полис ОСАГО", true, ""],
  ["Диагностическая карта", true, ""],
  ["Калибровка тахографа", true, ""],
  ["Путевой лист", false, ""],
  ["Свидетельство СПС (ATP) на реф", true, ""],
  ["Свидетельство ДОПОГ", true, ""],
  ["Зелёная карта", true, ""],
  ["Медкнижка", true, "med"],
  ["Санпаспорт", true, "san"]
];

export function emptyPhase(): ShiftPhasePayload {
  return {
    time: "",
    place: "",
    odo: "",
    fuel: "",
    reefer: "",
    temp: "",
    signed_at: null,
    damages: [],
    checks: CHECKS.map((name) => ({ id: uid(), name, st: null, note: "" })),
    docs: DEFAULT_DOCS.map(([name, needsExp, kind]) => ({
      id: uid(),
      name,
      needs_exp: needsExp,
      has: null,
      exp: "",
      kind,
      d1: "",
      d2: "",
      custom: false
    })),
    photos_meta: {}
  };
}

export function ensurePhase(raw?: Partial<ShiftPhasePayload> | null): ShiftPhasePayload {
  const base = emptyPhase();
  if (!raw) return base;
  return {
    ...base,
    ...raw,
    damages: Array.isArray(raw.damages) ? raw.damages : [],
    checks: Array.isArray(raw.checks) && raw.checks.length ? raw.checks : base.checks,
    docs: Array.isArray(raw.docs) && raw.docs.length ? raw.docs : base.docs,
    photos_meta: raw.photos_meta || {}
  };
}

function num(value: string | number | null | undefined): number | null {
  const text = String(value ?? "").trim().replace(",", ".");
  if (!text) return null;
  const n = Number(text);
  return Number.isFinite(n) ? n : null;
}

export function diffNum(a?: string | number | null, b?: string | number | null): number | null {
  const left = num(a);
  const right = num(b);
  if (left == null || right == null) return null;
  return Math.round((right - left) * 10) / 10;
}

export function fuelStats(intake: ShiftPhasePayload, handover: ShiftPhasePayload | null, refuels: ShiftRefuel[]) {
  const refuel = Math.round(refuels.reduce((sum, item) => sum + (num(item.liters) || 0), 0) * 10) / 10;
  let used: number | null = null;
  let per100: number | null = null;
  if (handover && intake.fuel !== "" && handover.fuel !== "") {
    used = Math.round(((num(intake.fuel) || 0) + refuel - (num(handover.fuel) || 0)) * 10) / 10;
    const km = diffNum(intake.odo, handover.odo);
    if (km != null && km > 0 && used >= 0) {
      per100 = Math.round((used / km) * 1000) / 10;
    }
  }
  return { refuel, count: refuels.length, used, per100 };
}

function addMonths(date: string, months: number): string {
  if (!date) return "";
  const d = new Date(`${date}T00:00:00`);
  if (Number.isNaN(d.getTime())) return "";
  const day = d.getDate();
  d.setMonth(d.getMonth() + months);
  if (d.getDate() < day) d.setDate(0);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function docExp(doc: ShiftDoc): string {
  if (!doc.kind) return doc.exp || "";
  const meta = KIND_META[doc.kind];
  if (!meta) return doc.exp || "";
  const a = addMonths(doc.d1, meta.p1);
  const b = addMonths(doc.d2, meta.p2);
  if (!a || !b) return "";
  return a < b ? a : b;
}

export function daysLeft(date: string): number | null {
  if (!date) return null;
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const end = new Date(`${date}T00:00:00`);
  if (Number.isNaN(end.getTime())) return null;
  return Math.round((end.getTime() - now.getTime()) / 86400000);
}

export function expStatus(doc: ShiftDoc): { c: "ok" | "warn" | "bad"; t: string } | null {
  if (doc.has !== "y" || !doc.needs_exp) return null;
  if (doc.kind && (!doc.d1 || !doc.d2)) return { c: "warn", t: "Укажите даты" };
  const d = daysLeft(docExp(doc));
  if (d == null) return { c: "warn", t: "Укажите срок" };
  if (d < 0) return { c: "bad", t: `Просрочен ${Math.abs(d)} дн.` };
  if (d === 0) return { c: "bad", t: "Истекает сегодня" };
  if (d <= WARN_DAYS) return { c: "warn", t: `Осталось ${d} дн.` };
  return { c: "ok", t: `Действует, ${d} дн.` };
}

export function slotLabel(slot: string): string {
  if (slot === "sign") return "Подпись";
  if (slot.startsWith("dmg:")) return "Повреждение";
  if (slot.startsWith("doc:")) return "Фото документа";
  if (slot.startsWith("rcpt:")) return "Чек заправки";
  return ALL_SLOTS.find((item) => item.k === slot)?.n || slot;
}

export function analyseShift(input: {
  driver_name: string;
  truck: string;
  intake: ShiftPhasePayload;
  handover: ShiftPhasePayload | null;
  photoKeys: string[];
  phase: ShiftPhase;
}): Array<["bad" | "warn" | "ok", string]> {
  const { driver_name, truck, intake, handover, photoKeys, phase } = input;
  const p = phase === "end" ? handover : intake;
  const out: Array<["bad" | "warn" | "ok", string]> = [];
  if (!p) {
    out.push(["bad", "Нет данных этапа"]);
    return out;
  }
  const keys = new Set(photoKeys);
  if (phase === "start") {
    if (!driver_name.trim()) out.push(["bad", "Не указан водитель"]);
    if (!truck.trim()) out.push(["bad", "Не указан госномер тягача"]);
  } else if (!p.time) {
    out.push(["bad", "Не указано время окончания вахты"]);
  }
  const miss = ALL_SLOTS.filter((item) => item.req && !keys.has(item.k)).map((item) => item.n);
  if (miss.length) out.push(["bad", `Нет фото: ${miss.join(", ").toLowerCase()}`]);
  if (p.odo === "") out.push(["bad", "Не внесены показания одометра"]);
  if (p.fuel === "") out.push(["bad", "Не внесён остаток топлива"]);
  if (p.reefer === "") out.push(["bad", "Не внесены моточасы рефрижератора"]);
  const dm = p.damages.length;
  if (phase === "start" && dm) out.push(["warn", `Зафиксировано повреждений при приёмке: ${dm}`]);
  if (phase === "end" && dm) out.push(["warn", `Повреждений при сдаче: ${dm} (при приёмке было ${intake.damages.length})`]);
  if (!p.signed_at && !keys.has("sign")) out.push(["warn", "Нет подписи водителя"]);
  const nd = p.damages.filter((item) => !item.note.trim()).length;
  if (nd) out.push(["warn", `Нет описания у повреждений: ${nd}`]);
  if (phase === "end") {
    const dk = diffNum(intake.odo, p.odo);
    const dh = diffNum(intake.reefer, p.reefer);
    if (dk != null && dk < 0) out.push(["bad", `Пробег на сдаче меньше, чем на приёмке (${fmtNum(intake.odo)} км)`]);
    if (dh != null && dh < 0) out.push(["bad", `Моточасы на сдаче меньше, чем на приёмке (${fmtNum(intake.reefer)})`]);
  }
  const unset = p.checks.filter((item) => item.st == null).length;
  if (unset) out.push(["warn", `Не проверено пунктов состояния: ${unset}`]);
  p.checks.filter((item) => item.st === "bad").forEach((item) => {
    out.push(["bad", `Неисправно: ${item.name}${item.note.trim() ? ` — ${item.note.trim()}` : ""}`]);
  });
  const unk = p.docs.filter((item) => item.has == null).length;
  if (unk) out.push(["warn", `Не отмечено документов: ${unk}`]);
  p.docs.filter((item) => item.has === "n").forEach((item) => {
    const was = phase === "end" && intake.docs.some((doc) => doc.name === item.name && doc.has === "y");
    out.push(["bad", `Нет документа: ${item.name}${was ? " (был на приёмке)" : ""}`]);
  });
  p.docs.forEach((doc) => {
    const st = expStatus(doc);
    if (st && st.c !== "ok") {
      const until = docExp(doc);
      out.push([st.c, `${doc.name}: ${st.t.toLowerCase()}${until ? ` (до ${fmtD(until)})` : ""}`]);
    }
  });
  return out;
}

export function stepDone(input: {
  driver_name: string;
  truck: string;
  payload: ShiftPhasePayload;
  photoKeys: string[];
  phase: ShiftPhase;
  step: number;
  workflow: ShiftWorkflow;
}): boolean {
  const { driver_name, truck, payload, photoKeys, phase, step, workflow } = input;
  const keys = new Set(photoKeys);
  if (step === 0) return phase === "start" ? Boolean(driver_name.trim() && truck.trim()) : Boolean(payload.time);
  if (step === 1) {
    return ALL_SLOTS.every((item) => !item.req || keys.has(item.k)) && payload.odo !== "" && payload.fuel !== "" && payload.reefer !== "";
  }
  if (step === 2) {
    return payload.checks.every((item) => item.st != null) && payload.docs.every((item) => item.has != null);
  }
  return phase === "start" ? workflow !== "draft" : workflow === "closed";
}

export function reportText(input: {
  driver_name: string;
  truck: string;
  trailer: string;
  intake: ShiftPhasePayload;
  handover: ShiftPhasePayload | null;
  refuels: ShiftRefuel[];
}): string {
  const lines = [
    `ВАХТА ${input.truck || ""}`.trim(),
    `Водитель: ${input.driver_name || "—"}`,
    `Тягач: ${input.truck || "—"}   Прицеп: ${input.trailer || "—"}`
  ];
  if (input.handover) {
    const dk = diffNum(input.intake.odo, input.handover.odo);
    const dh = diffNum(input.intake.reefer, input.handover.reefer);
    const fuel = fuelStats(input.intake, input.handover, input.refuels);
    lines.push(
      `Итого: пробег ${dk == null ? "—" : `${fmtNum(dk)} км`}, моточасы рефа ${dh == null ? "—" : fmtNum(dh)}`,
      `Топливо: заправлено ${fmtNum(fuel.refuel)} л (${fuel.count}), израсходовано ${fuel.used == null ? "—" : `${fmtNum(fuel.used)} л`}`
    );
  }
  const parts: Array<[string, ShiftPhasePayload]> = [["Приёмка ТС", input.intake]];
  if (input.handover) parts.push(["Сдача ТС", input.handover]);
  for (const [title, p] of parts) {
    lines.push("", title);
    lines.push(`Время: ${p.time ? fmtDT(p.time) : "—"}`);
    lines.push(`Место: ${p.place || "—"}`);
    lines.push(`Одометр: ${fmtNum(p.odo)} км`);
    lines.push(`Топливо: ${fmtNum(p.fuel)} л`);
    lines.push(`Моточасы рефа: ${fmtNum(p.reefer)}`);
  }
  return lines.join("\n");
}

export function workflowLabel(status?: string | null): string {
  if (status === "draft") return "Приёмка";
  if (status === "active") return "Идёт вахта";
  if (status === "closing") return "Сдача";
  if (status === "closed" || status === "ended") return "Завершена";
  return status === "active" ? "Действует" : "Закончена";
}
