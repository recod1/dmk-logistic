export type RoleCode = "driver" | "logistic" | "accountant" | "admin" | "superadmin";

export const ROLE_LABELS_RU: Record<RoleCode, string> = {
  driver: "Водитель",
  logistic: "Логист",
  accountant: "Бухгалтер",
  admin: "Администратор",
  superadmin: "Супер-админ"
};

export const ROLE_OPTIONS: Array<{ role_code: RoleCode; role_label: string }> = (
  Object.entries(ROLE_LABELS_RU) as Array<[RoleCode, string]>
).map(([role_code, role_label]) => ({ role_code, role_label }));

export function isAdminRole(roleCode: string): boolean {
  return roleCode === "admin" || roleCode === "superadmin";
}

export function isRouteManagerRole(roleCode: string): boolean {
  return roleCode === "admin" || roleCode === "superadmin" || roleCode === "logistic" || roleCode === "accountant";
}

export function isLogisticRole(roleCode: string): boolean {
  return roleCode === "logistic";
}

export function isAccountantRole(roleCode: string): boolean {
  return roleCode === "accountant";
}

