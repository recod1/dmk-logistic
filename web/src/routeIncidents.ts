export type IncidentKind = "delay" | "breakdown" | "no_pass" | "no_data" | "not_unloading" | "return";

export interface RouteIncident {
  id: number;
  route_id: string;
  point_id?: number | null;
  kind: IncidentKind | string;
  kind_label: string;
  status: "open" | "resolved" | string;
  comment: string;
  cargo_name: string;
  quantity: string;
  authorized_by: string;
  return_stage: string;
  return_stage_label: string;
  next_return_stage: string | null;
  next_return_stage_label: string;
  needs_photo: boolean;
  return_warning: string;
  follow_up_code: string | null;
  follow_up_label: string | null;
  created_at: string | null;
}

export const PROBLEM_CHOICES: Array<{ kind: IncidentKind; label: string; needsReason: boolean; followUp?: string }> = [
  { kind: "delay", label: "Опоздание", needsReason: true },
  { kind: "breakdown", label: "Поломка", needsReason: true, followUp: "Поломка устранена" },
  { kind: "no_pass", label: "Нет пропуска на въезд", needsReason: false, followUp: "Пропуск получен" },
  { kind: "no_data", label: "Нет данных на загр/выгр", needsReason: false, followUp: "Данные получены" },
  { kind: "not_unloading", label: "Не выгружают", needsReason: true },
  { kind: "return", label: "Возврат", needsReason: true }
];

export const RETURN_WARNING =
  "‼️ЗАБИРАТЬ ВОЗВРАТ ТОЛЬКО ПОСЛЕ ПОДТВЕРЖДЕНИЯ ОТ ЛОГИСТА (в любом мессенджере или по телефону)‼️";
