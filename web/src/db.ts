import Dexie, { type EntityTable } from "dexie";

import type { EventPayload, RouteDto } from "./types";

export interface ActiveRouteSnapshot {
  key: "active";
  route: RouteDto | null;
  updatedAt: string;
}

export interface OutboxEvent extends EventPayload {
  id?: number;
  device_id: string;
  created_at: string;
}

const db = new Dexie("dmk-mobile-db") as Dexie & {
  activeRoute: EntityTable<ActiveRouteSnapshot, "key">;
  outbox: EntityTable<OutboxEvent, "id">;
};

db.version(1).stores({
  activeRoute: "key",
  outbox: "++id,client_event_id,point_id,created_at"
});

export async function saveActiveRoute(route: RouteDto | null): Promise<void> {
  await db.activeRoute.put({
    key: "active",
    route,
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

export async function getOutboxEvents(deviceId: string): Promise<OutboxEvent[]> {
  return db.outbox.where("created_at").above("").filter((item) => item.device_id === deviceId).toArray();
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

export default db;

