import { loadAuthSession } from "./db";
import { resolveApiBase } from "./offlinePrefetch";

export const DRIVER_PRESENCE_SYNC_TAG = "dmk-driver-presence";

export async function reportPresenceFromSession(payload?: { lat?: number; lng?: number }): Promise<boolean> {
  const session = await loadAuthSession();
  if (!session?.token || session.roleCode !== "driver") {
    return false;
  }
  const apiBase = resolveApiBase(session.apiBase);
  try {
    const response = await fetch(`${apiBase}/v1/mobile/presence`, {
      method: "POST",
      cache: "no-store",
      keepalive: true,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.token}`
      },
      body: JSON.stringify(payload || {})
    });
    return response.ok;
  } catch {
    return false;
  }
}
