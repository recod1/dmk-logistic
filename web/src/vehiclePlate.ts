const LATIN_TO_CYR: Record<string, string> = {
  A: "А",
  B: "В",
  E: "Е",
  K: "К",
  M: "М",
  H: "Н",
  O: "О",
  P: "Р",
  C: "С",
  T: "Т",
  Y: "У",
  X: "Х"
};

const PATTERN_STD = /^[А-ЯA-Z]\d{3}[А-ЯA-Z]{2}\d{2,3}$/;
const PATTERN_SPEC = /^[А-ЯA-Z]{2}\d{6}$/;

export const PLATE_HINT =
  "Формат: А111АА22 / А111АА222 или ЕН068477 (2 буквы + 6 цифр)";

export function normalizePlate(raw?: string | null): string {
  const text = (raw || "").trim().toUpperCase().replace(/[\s-]/g, "");
  return text.replace(/[ABEKMHOPCTYX]/g, (ch) => LATIN_TO_CYR[ch] || ch);
}

export function isValidPlate(raw?: string | null): boolean {
  const plate = normalizePlate(raw);
  if (!plate) {
    return false;
  }
  return PATTERN_STD.test(plate) || PATTERN_SPEC.test(plate);
}
