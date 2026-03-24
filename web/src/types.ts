export type PointStatus = "new" | "process" | "registration" | "load" | "docs" | "success";

export interface AuthUser {
  id: number;
  login: string;
  role_code: string;
  role_label: string;
  full_name: string | null;
  phone: string | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_at: string;
  user: AuthUser;
}

export interface PointDto {
  id: number;
  route_id: string;
  type_point: string;
  place_point: string;
  date_point: string;
  status: PointStatus;
  time_accepted: string | null;
  time_registration: string | null;
  time_put_on_gate: string | null;
  time_docs: string | null;
  time_departure: string | null;
}

export interface RouteDto {
  id: string;
  status: string;
  number_auto: string;
  temperature: string;
  dispatcher_contacts: string;
  registration_number: string;
  trailer_number: string;
  accepted_at: string | null;
  points: PointDto[];
}

export interface ActiveRouteResponse {
  route: RouteDto | null;
}

export interface EventPayload {
  client_event_id: string;
  occurred_at_client: string;
  point_id: number;
  to_status: Exclude<PointStatus, "new">;
}

export interface BatchResultItem {
  client_event_id: string;
  point_id: number;
  to_status: string;
  applied: boolean;
  duplicate: boolean;
  error: string | null;
  server_received_at: string;
  server_time_delta_ms?: number;
}

export interface BatchResponse {
  items: BatchResultItem[];
  applied: number;
  received: number;
  server_received_at: string;
}

export interface AdminUser {
  id: number;
  login: string;
  role_code: string;
  role_label: string;
  full_name: string | null;
  phone: string | null;
  is_active: boolean;
  created_at: string | null;
}

export interface AdminUsersListResponse {
  items: AdminUser[];
}

export interface AdminUserCreatePayload {
  login: string;
  password: string;
  role_code: string;
  full_name?: string | null;
  phone?: string | null;
}

export interface AdminUserUpdatePayload {
  login?: string;
  password?: string;
  role_code?: string;
  full_name?: string | null;
  phone?: string | null;
  is_active?: boolean;
}

export interface DriverOption {
  id: number;
  login: string;
  full_name: string | null;
  phone: string | null;
  role_code: string;
  role_label: string;
  is_active: boolean;
}

export interface AdminRoutePointPayload {
  type_point: string;
  place_point: string;
  date_point: string;
  order_index?: number;
}

export interface AdminRouteCreatePayload {
  route_id: string;
  driver_user_id: number;
  number_auto?: string;
  temperature?: string;
  dispatcher_contacts?: string;
  registration_number?: string;
  trailer_number?: string;
  points?: AdminRoutePointPayload[];
}

export type RouteWorkflowStatus = "new" | "process" | "success" | "cancelled";

export interface AdminRoute {
  id: string;
  status: RouteWorkflowStatus;
  number_auto: string;
  temperature: string;
  dispatcher_contacts: string;
  registration_number: string;
  trailer_number: string;
  accepted_at: string | null;
  created_at: string | null;
  driver: DriverOption | null;
  created_by: DriverOption | null;
  points_count: number;
  points: Array<
    {
      id: number;
      order_index: number;
      type_point: string;
      place_point: string;
      date_point: string;
      status: string;
      time_accepted: string | null;
      time_registration: string | null;
      time_put_on_gate: string | null;
      time_docs: string | null;
      time_departure: string | null;
    }
  > | null;
}

export interface AdminRoutesListResponse {
  items: AdminRoute[];
}

export interface DriversResponse {
  items: DriverOption[];
}

export interface AdminRouteActionPayload {
  reason?: string;
}

export interface RouteStatusUpdatePayload {
  status: RouteWorkflowStatus;
}

