import type { CheckState } from "./shiftInspection";
import { fmtD, fmtDT } from "./shiftInspection";

export type DailyCheckStatus = "pending" | "done" | "skipped";

export interface DailyCheckItem {
  key: string;
  name: string;
  st: CheckState;
  note: string;
}

export interface ShiftDailyCheck {
  id: number;
  shift_id: number;
  check_date: string;
  status: DailyCheckStatus;
  items: DailyCheckItem[];
  notified_at: string | null;
  completed_at: string | null;
  skipped_at: string | null;
  created_at: string | null;
  has_fault?: boolean;
}

export const DAILY_CHECKS: Array<{ key: string; name: string }> = [
  { key: "tires", name: "Шины" },
  { key: "lights", name: "Световые приборы" },
  { key: "oil", name: "Масло" },
  { key: "coolant", name: "Антифриз" },
  { key: "brakes", name: "Тормоза" },
  { key: "clutch", name: "Сцепление" },
  { key: "tacho", name: "Тахограф" },
  { key: "reefer", name: "Рефрижератор" }
];

export function emptyDailyItems(): DailyCheckItem[] {
  return DAILY_CHECKS.map((item) => ({ key: item.key, name: item.name, st: null, note: "" }));
}

export function hydrateDailyItems(items?: DailyCheckItem[] | null): DailyCheckItem[] {
  const byKey = new Map((items || []).map((item) => [item.key, item]));
  return DAILY_CHECKS.map((spec) => {
    const src = byKey.get(spec.key);
    const st = src?.st === "ok" || src?.st === "bad" ? src.st : null;
    return { key: spec.key, name: spec.name, st, note: (src?.note || "").trim() };
  });
}

export function dailyStatusLabel(status: DailyCheckStatus | string): string {
  if (status === "done") return "Выполнена";
  if (status === "skipped") return "Пропущена";
  return "Ожидает";
}

export function dailyItemLabel(item: DailyCheckItem): string {
  if (item.st === "ok") return "Норма";
  if (item.st === "bad") return "Неисправно";
  return "Не проверено";
}

export function dailyDateLabel(iso?: string | null): string {
  return fmtD(iso);
}

export function dailyWhenLabel(check: ShiftDailyCheck): string {
  if (check.status === "done") return fmtDT(check.completed_at);
  if (check.status === "skipped") return fmtDT(check.skipped_at);
  return "ещё не закрыта";
}
