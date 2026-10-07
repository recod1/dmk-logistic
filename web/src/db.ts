import Dexie, { type EntityTable } from "dexie";

import type { EventPayload, PointStatus, RouteDto, DriverRouteListItem } from "./types";

export interface ActiveRouteSnapshot {
  key: "active";
  route: RouteDto | null;
  updatedAt: string;
}

export interface OutboxEvent extends EventPayload {
  id?: number;
  device_id: string;
  user_id?: number;
  created_at: string;
}

export interface PendingDocBlob {
  local_key: string;
  point_id: number;
  route_id: string;
  blob: Blob;
  content_type: string;
  created_at: string;
}

export interface PointStatusOverlay {
  id?: number;
  route_id: string;
  point_id: number;
  status: Exclude<PointStatus, "new">;
  occurred_at_client: string;
  time?: string | null;
  odometer?: string | null;
  time_source?: string | null;
  odometer_source?: string | null;
  estimated_arrival?: string | null;
  previous_status?: PointStatus | null;
  updated_at: string;
}

export type ActionKind =
  | "revert"
  | "chat_route"
  | "chat_room"
  | "chat_salary"
  | "location"
  | "salary_confirm"
  | "salary_comment";

export interface ActionQueueItem {
  id?: number;
  client_id: string;
  kind: ActionKind;
  created_at: string;
  device_id: string;
  user_id?: number;
  payload: {
    route_id?: string;
    point_id?: number;
    room_id?: number;
    salary_id?: number;
    text?: string;
    lat?: number;
    lng?: number;
  };
  last_error?: string | null;
}

export interface MessageSnapshotRow {
  key: string;
  items: unknown[];
  updatedAt: string;
}

export interface DriverRoutesCacheRow {
  key: "driver";
  assigned: DriverRouteListItem[];
  history: DriverRouteListItem[];
  active_route_id: string | null;
  updatedAt: string;
}

export interface RouteSnapshotRow {
  id: string;
  route: RouteDto;
  updatedAt: string;
}

export interface PendingAcceptRow {
  route_id: string;
  created_at: string;
}

export interface AuthSessionRow {
  key: "current";
  token: string;
  apiBase: string;
  roleCode: string;
  updatedAt: string;
}

const db = new Dexie("dmk-mobile-db") as Dexie & {
  activeRoute: EntityTable<ActiveRouteSnapshot, "key">;
  outbox: EntityTable<OutboxEvent, "id">;
  pointOverlay: EntityTable<PointStatusOverlay, "id">;
  pendingDocBlobs: EntityTable<PendingDocBlob, "local_key">;
  driverRoutesCache: EntityTable<DriverRoutesCacheRow, "key">;
  routeSnapshots: EntityTable<RouteSnapshotRow, "id">;
  pendingAccepts: EntityTable<PendingAcceptRow, "route_id">;
  authSession: EntityTable<AuthSessionRow, "key">;
  actionQueue: EntityTable<ActionQueueItem, "id">;
  messageSnapshots: EntityTable<MessageSnapshotRow, "key">;
};

db.version(1).stores({
  activeRoute: "key",
  outbox: "++id,client_event_id,point_id,created_at"
});

db.version(2).stores({
  activeRoute: "key",
  outbox: "++id,client_event_id,point_id,created_at",
  pointOverlay: "++id,route_id,point_id,[route_id+point_id],updated_at"
});

db.version(3).stores({
  activeRoute: "key",
  outbox: "++id,client_event_id,point_id,created_at",
  pointOverlay: "++id,route_id,point_id,[route_id+point_id],updated_at"
});

db.version(4).stores({
  activeRoute: "key",
  outbox: "++id,client_event_id,point_id,created_at",
  pointOverlay: "++id,route_id,point_id,[route_id+point_id],updated_at",
  pendingDocBlobs: "local_key,point_id,route_id,created_at"
});

db.version(5).stores({
  activeRoute: "key",
  outbox: "++id,client_event_id,point_id,created_at",
  pointOverlay: "++id,route_id,point_id,[route_id+point_id],updated_at",
  pendingDocBlobs: "local_key,point_id,route_id,created_at",
  driverRoutesCache: "key",
  routeSnapshots: "id",
  pendingAccepts: "route_id,created_at"
});

db.version(6).stores({
  activeRoute: "key",
  outbox: "++id,client_event_id,point_id,created_at",
  pointOverlay: "++id,route_id,point_id,[route_id+point_id],updated_at",
  pendingDocBlobs: "local_key,point_id,route_id,created_at",
  driverRoutesCache: "key",
  routeSnapshots: "id",
  pendingAccepts: "route_id,created_at",
  authSession: "key"
});

db.version(7).stores({
  activeRoute: "key",
  outbox: "++id,client_event_id,point_id,created_at,user_id",
  pointOverlay: "++id,route_id,point_id,[route_id+point_id],updated_at",
  pendingDocBlobs: "local_key,point_id,route_id,created_at",
  driverRoutesCache: "key",
  routeSnapshots: "id",
  pendingAccepts: "route_id,created_at",
  authSession: "key"
});

db.version(8).stores({
  activeRoute: "key",
  outbox: "++id,client_event_id,point_id,created_at,user_id",
  pointOverlay: "++id,route_id,point_id,[route_id+point_id],updated_at",
  pendingDocBlobs: "local_key,point_id,route_id,created_at",
  driverRoutesCache: "key",
  routeSnapshots: "id",
  pendingAccepts: "route_id,created_at",
  authSession: "key",
  actionQueue: "++id,client_id,kind,created_at,device_id,user_id",
  messageSnapshots: "key"
});

function toPlainObject<T>(value: T): T {
  if (value === null || value === undefined) {
    return value;
  }
  if (typeof structuredClone === "function") {
    try {
      return structuredClone(value);
    } catch {
      // Vue reactive proxies may throw DataCloneError with structuredClone.
    }
  }
  return JSON.parse(JSON.stringify(value)) as T;
}

export async function saveActiveRoute(route: RouteDto | null): Promise<void> {
  await db.activeRoute.put({
    key: "active",
    route: toPlainObject(route),
    updatedAt: new Date().toISOString()
  });
}

export async function loadActiveRoute(): Promise<RouteDto | null> {
  const row = await db.activeRoute.get("active");
  return row?.route ?? null;
}

export async function addOutboxEvent(event: OutboxEvent): Promise<void> {
  await db.outbox.add(event);
}

export async function getOutboxEvents(deviceId: string, userId?: number | null): Promise<OutboxEvent[]> {
  return db.outbox
    .where("created_at")
    .above("")
    .filter((item) => {
      if (item.device_id !== deviceId) {
        return false;
      }
      if (userId && item.user_id && item.user_id !== userId) {
        return false;
      }
      return true;
    })
    .toArray();
}

export async function listPendingDocBlobs(): Promise<PendingDocBlob[]> {
  return db.pendingDocBlobs.toArray();
}

export async function clearLocalUserData(): Promise<void> {
  await Promise.all([
    db.activeRoute.clear(),
    db.outbox.clear(),
    db.pointOverlay.clear(),
    db.pendingDocBlobs.clear(),
    db.driverRoutesCache.clear(),
    db.routeSnapshots.clear(),
    db.pendingAccepts.clear(),
    db.authSession.clear(),
    db.actionQueue.clear(),
    db.messageSnapshots.clear()
  ]);
}

export async function removeOutboxByClientEventIds(ids: string[]): Promise<void> {
  if (!ids.length) {
    return;
  }
  const rows = await db.outbox.where("client_event_id").anyOf(ids).toArray();
  if (!rows.length) {
    return;
  }
  await db.outbox.bulkDelete(rows.map((row) => row.id!).filter(Boolean));
}

export async function savePointOverlay(
  routeId: string,
  pointId: number,
  status: Exclude<PointStatus, "new">,
  occurredAtClient: string,
  extras?: {
    time?: string | null;
    odometer?: string | null;
    time_source?: string | null;
    odometer_source?: string | null;
    estimated_arrival?: string | null;
    previous_status?: PointStatus | null;
  }
): Promise<void> {
  const existing = await db.pointOverlay.where("[route_id+point_id]").equals([routeId, pointId]).first();
  const payload: PointStatusOverlay = {
    route_id: routeId,
    point_id: pointId,
    status,
    occurred_at_client: occurredAtClient,
    time: extras?.time ?? occurredAtClient,
    odometer: extras?.odometer ?? null,
    time_source: extras?.time_source ?? null,
    odometer_source: extras?.odometer_source ?? null,
    estimated_arrival: extras?.estimated_arrival ?? null,
    previous_status: extras?.previous_status ?? null,
    updated_at: new Date().toISOString()
  };
  if (existing?.id) {
    await db.pointOverlay.update(existing.id, payload);
    return;
  }
  await db.pointOverlay.add(payload);
}

export async function getPointOverlays(routeId: string): Promise<PointStatusOverlay[]> {
  return db.pointOverlay.where("route_id").equals(routeId).sortBy("updated_at");
}

export async function savePendingDocBlob(row: PendingDocBlob): Promise<void> {
  await db.pendingDocBlobs.put(row);
}

export async function getPendingDocBlob(localKey: string): Promise<PendingDocBlob | undefined> {
  return db.pendingDocBlobs.get(localKey);
}

export async function removePendingDocBlobs(localKeys: string[]): Promise<void> {
  if (!localKeys.length) {
    return;
  }
  await db.pendingDocBlobs.bulkDelete(localKeys);
}

export async function updateOutboxEventByClientId(
  clientEventId: string,
  patch: Partial<Pick<OutboxEvent, "document_file_ids" | "document_local_keys">>
): Promise<void> {
  const row = await db.outbox.where("client_event_id").equals(clientEventId).first();
  if (!row?.id) {
    return;
  }
  const next: OutboxEvent = { ...row, ...patch };
  await db.outbox.put(next);
}

export async function removePointOverlays(routeId: string, pointIds: number[]): Promise<void> {
  if (!pointIds.length) {
    return;
  }
  const rows = await db.pointOverlay.where("route_id").equals(routeId).toArray();
  const idsToDelete = rows.filter((row) => pointIds.includes(row.point_id)).map((row) => row.id!).filter(Boolean);
  if (!idsToDelete.length) {
    return;
  }
  await db.pointOverlay.bulkDelete(idsToDelete);
}

export async function saveDriverRoutesCache(row: Omit<DriverRoutesCacheRow, "key" | "updatedAt">): Promise<void> {
  await db.driverRoutesCache.put({
    key: "driver",
    assigned: toPlainObject(row.assigned),
    history: toPlainObject(row.history),
    active_route_id: row.active_route_id,
    updatedAt: new Date().toISOString()
  });
}

export async function loadDriverRoutesCache(): Promise<DriverRoutesCacheRow | undefined> {
  return db.driverRoutesCache.get("driver");
}

export async function saveRouteSnapshot(route: RouteDto): Promise<void> {
  await db.routeSnapshots.put({
    id: route.id,
    route: toPlainObject(route),
    updatedAt: new Date().toISOString()
  });
}

export async function loadRouteSnapshot(routeId: string): Promise<RouteDto | null> {
  const row = await db.routeSnapshots.get(routeId);
  return row?.route ?? null;
}

export async function addPendingAccept(routeId: string): Promise<void> {
  await db.pendingAccepts.put({
    route_id: routeId,
    created_at: new Date().toISOString()
  });
}

export async function getPendingAccepts(): Promise<PendingAcceptRow[]> {
  return db.pendingAccepts.orderBy("created_at").toArray();
}

export async function removePendingAccept(routeId: string): Promise<void> {
  await db.pendingAccepts.delete(routeId);
}

export async function hasPendingAccept(routeId: string): Promise<boolean> {
  const row = await db.pendingAccepts.get(routeId);
  return Boolean(row);
}

export async function saveAuthSession(row: Omit<AuthSessionRow, "key" | "updatedAt">): Promise<void> {
  await db.authSession.put({
    key: "current",
    token: row.token,
    apiBase: row.apiBase,
    roleCode: row.roleCode,
    updatedAt: new Date().toISOString()
  });
}

export async function loadAuthSession(): Promise<AuthSessionRow | undefined> {
  return db.authSession.get("current");
}

export async function clearAuthSession(): Promise<void> {
  await db.authSession.delete("current");
}

export async function addAction(item: ActionQueueItem): Promise<void> {
  await db.actionQueue.add(item);
}

export async function listActions(deviceId: string, userId?: number | null): Promise<ActionQueueItem[]> {
  return db.actionQueue
    .orderBy("created_at")
    .filter((item) => {
      if (item.device_id !== deviceId) {
        return false;
      }
      if (userId && item.user_id && item.user_id !== userId) {
        return false;
      }
      return true;
    })
    .toArray();
}

export async function removeActionsByClientIds(ids: string[]): Promise<void> {
  if (!ids.length) {
    return;
  }
  const rows = await db.actionQueue.where("client_id").anyOf(ids).toArray();
  if (!rows.length) {
    return;
  }
  await db.actionQueue.bulkDelete(rows.map((row) => row.id!).filter(Boolean));
}

export async function saveMessageSnapshot(key: string, items: unknown[]): Promise<void> {
  await db.messageSnapshots.put({
    key,
    items: toPlainObject(items),
    updatedAt: new Date().toISOString()
  });
}

export async function loadMessageSnapshot<T>(key: string): Promise<T[] | null> {
  const row = await db.messageSnapshots.get(key);
  return (row?.items as T[] | undefined) ?? null;
}

export async function getDriverQueueCounts(
  deviceId: string
): Promise<{ outbox: number; docs: number; accepts: number; actions: number }> {
  const [outboxRows, docs, accepts, actions] = await Promise.all([
    db.outbox.toArray(),
    db.pendingDocBlobs.count(),
    db.pendingAccepts.count(),
    db.actionQueue.toArray()
  ]);
  return {
    outbox: outboxRows.filter((item) => item.device_id === deviceId).length,
    docs,
    accepts,
    actions: actions.filter((item) => item.device_id === deviceId).length
  };
}

export default db;

