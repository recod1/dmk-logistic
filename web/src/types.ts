export type PointStatus = "new" | "process" | "registration" | "load" | "docs" | "success";

export interface AuthUser {
  id: number;
  login: string;
  role: string;
  full_name: string | null;
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

