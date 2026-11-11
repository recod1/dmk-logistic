import { expStatus, type DocHas, type ShiftDoc } from "./shiftInspection";

export type EntityKind = "vehicle" | "trailer" | "driver";

export interface EntityDocSpec {
  key: string;
  name: string;
  needs_exp: boolean;
  kind: string;
}

export interface EntityDocValue {
  has: DocHas;
  exp: string;
  d1: string;
  d2: string;
  note?: string;
  kind?: string;
}

export type EntityDocsMap = Record<string, EntityDocValue>;

export const ENTITY_DOC_SPECS: Record<EntityKind, EntityDocSpec[]> = {
  vehicle: [
    { key: "sts", name: "СТС тягача", needs_exp: false, kind: "" },
    { key: "osago", name: "Полис ОСАГО", needs_exp: true, kind: "" },
    { key: "diagnostic", name: "Диагностическая карта", needs_exp: true, kind: "" },
    { key: "tacho_calib", name: "Калибровка тахографа", needs_exp: true, kind: "" },
    { key: "green_card", name: "Зелёная карта", needs_exp: true, kind: "" },
    { key: "dopog", name: "Свидетельство ДОПОГ (ТС)", needs_exp: true, kind: "" }
  ],
  trailer: [
    { key: "sts", name: "СТС прицепа", needs_exp: false, kind: "" },
    { key: "atp", name: "Свидетельство СПС (ATP) на реф", needs_exp: true, kind: "" },
    { key: "san", name: "Санпаспорт", needs_exp: true, kind: "san" },
    { key: "diagnostic", name: "Диагностическая карта прицепа", needs_exp: true, kind: "" }
  ],
  driver: [
    { key: "license", name: "Водительское удостоверение", needs_exp: true, kind: "" },
    { key: "tacho_card", name: "Карта водителя (тахограф)", needs_exp: true, kind: "" },
    { key: "med_cert", name: "Медицинская справка", needs_exp: true, kind: "" },
    { key: "medbook", name: "Медкнижка", needs_exp: true, kind: "med" },
    { key: "dopog", name: "Свидетельство ДОПОГ", needs_exp: true, kind: "" }
  ]
};

export const SHIFT_DOC_BINDINGS: Record<string, { entity: EntityKind; key: string }> = {
  "Водительское удостоверение": { entity: "driver", key: "license" },
  "Карта водителя (тахограф)": { entity: "driver", key: "tacho_card" },
  "Медицинская справка": { entity: "driver", key: "med_cert" },
  Медкнижка: { entity: "driver", key: "medbook" },
  "Свидетельство ДОПОГ": { entity: "driver", key: "dopog" },
  "СТС тягача": { entity: "vehicle", key: "sts" },
  "Полис ОСАГО": { entity: "vehicle", key: "osago" },
  "Диагностическая карта": { entity: "vehicle", key: "diagnostic" },
  "Калибровка тахографа": { entity: "vehicle", key: "tacho_calib" },
  "Зелёная карта": { entity: "vehicle", key: "green_card" },
  "СТС прицепа": { entity: "trailer", key: "sts" },
  "Свидетельство СПС (ATP) на реф": { entity: "trailer", key: "atp" },
  Санпаспорт: { entity: "trailer", key: "san" }
};

export function emptyEntityDocs(kind: EntityKind): EntityDocsMap {
  const out: EntityDocsMap = {};
  for (const spec of ENTITY_DOC_SPECS[kind]) {
    out[spec.key] = { has: null, exp: "", d1: "", d2: "", note: "", kind: spec.kind };
  }
  return out;
}

export function normalizeEntityDocs(raw: EntityDocsMap | null | undefined, kind: EntityKind): EntityDocsMap {
  const base = emptyEntityDocs(kind);
  if (!raw) return base;
  for (const spec of ENTITY_DOC_SPECS[kind]) {
    const src = raw[spec.key];
    if (!src) continue;
    const has = src.has === "y" || src.has === "n" || src.has === "x" ? src.has : null;
    base[spec.key] = {
      has,
      exp: src.exp || "",
      d1: src.d1 || "",
      d2: src.d2 || "",
      note: src.note || "",
      kind: spec.kind
    };
  }
  return base;
}

export function applyProfileToShiftDocs(
  docs: ShiftDoc[],
  profile: EntityDocsMap | null | undefined,
  entity: EntityKind
): void {
  if (!profile) return;
  for (const doc of docs) {
    const bind = SHIFT_DOC_BINDINGS[doc.name];
    if (!bind || bind.entity !== entity) continue;
    const saved = profile[bind.key];
    if (!saved?.has || doc.has != null) continue;
    doc.has = saved.has;
    doc.exp = saved.exp || doc.exp;
    doc.d1 = saved.d1 || doc.d1;
    doc.d2 = saved.d2 || doc.d2;
    if (saved.kind && !doc.kind) doc.kind = saved.kind;
  }
}

export function asShiftDoc(spec: EntityDocSpec, value: EntityDocValue): ShiftDoc {
  return {
    id: spec.key,
    name: spec.name,
    needs_exp: spec.needs_exp,
    has: value.has,
    exp: value.exp,
    kind: spec.kind || value.kind || "",
    d1: value.d1,
    d2: value.d2,
    custom: false
  };
}

export function entityDocStatus(spec: EntityDocSpec, value: EntityDocValue) {
  return expStatus(asShiftDoc(spec, value));
}
