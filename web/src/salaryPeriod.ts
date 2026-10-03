import type { SalaryRecord } from "./api";

export function ruDateToIso(value: string): string {
  const match = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec((value || "").trim());
  return match ? `${match[3]}-${match[2]}-${match[1]}` : "";
}

export function isoDateToRu(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec((value || "").trim());
  return match ? `${match[3]}.${match[2]}.${match[1]}` : "";
}

export type SalaryPeriodSummary = {
  days: number;
  mileage: number;
  load2: number;
  rate5: number;
  rate10: number;
  extraPoints: number;
  pallets: number;
  daily: number;
  salary: number;
};

function num(value: number | null | undefined): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

export function summarizeSalaryPeriod(items: SalaryRecord[]): SalaryPeriodSummary {
  const days = new Set<string>();
  const out: SalaryPeriodSummary = {
    days: 0,
    mileage: 0,
    load2: 0,
    rate5: 0,
    rate10: 0,
    extraPoints: 0,
    pallets: 0,
    daily: 0,
    salary: 0
  };
  for (const row of items) {
    const day = (row.date_salary || "").trim();
    if (day) days.add(day);
    out.mileage += num(row.mileage);
    out.load2 += num(row.load_2_trips);
    out.rate5 += num(row.rate_5km);
    out.rate10 += num(row.rate_10km);
    out.extraPoints += num(row.sum_add_point);
    out.pallets += num(row.pallets_hyper) + num(row.pallets_metro) + num(row.pallets_ashan);
    out.daily += num(row.sum_daily);
    out.salary += num(row.total);
  }
  out.days = days.size || items.length;
  return out;
}

export function formatMoney(value: number): string {
  return `${value.toFixed(2)} ₽`;
}
