import { loadAuthSession } from "./db";
import { resolveApiBase } from "./offlinePrefetch";

export type ChatDeliveryHint = {
  event_type?: string;
  route_id?: string | null;
  room_id?: number | string | null;
  salary_id?: number | string | null;
  chat_message_id?: number | string | null;
  salary_chat_message_id?: number | string | null;
};

function asPositiveInt(value: unknown): number | null {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n) || n <= 0) {
    return null;
  }
  return Math.trunc(n);
}

export function parseChatDeliveryHint(raw: ChatDeliveryHint | null | undefined): {
  kind: "route" | "room" | "salary";
  id: string | number;
  messageId: number;
} | null {
  if (!raw || (raw.event_type && raw.event_type !== "chat_message")) {
    return null;
  }
  const roomId = asPositiveInt(raw.room_id);
  const salaryId = asPositiveInt(raw.salary_id);
  const routeId = typeof raw.route_id === "string" ? raw.route_id.trim() : "";
  const salaryMsg = asPositiveInt(raw.salary_chat_message_id);
  const chatMsg = asPositiveInt(raw.chat_message_id);
  if (salaryId && salaryMsg) {
    return { kind: "salary", id: salaryId, messageId: salaryMsg };
  }
  if (roomId && chatMsg) {
    return { kind: "room", id: roomId, messageId: chatMsg };
  }
  if (routeId && chatMsg) {
    return { kind: "route", id: routeId, messageId: chatMsg };
  }
  return null;
}

export async function deliverChatFromPush(raw: ChatDeliveryHint | null | undefined): Promise<boolean> {
  const hint = parseChatDeliveryHint(raw);
  if (!hint) {
    return false;
  }
  const session = await loadAuthSession();
  if (!session?.token) {
    return false;
  }
  const apiBase = resolveApiBase(session.apiBase);
  let url = "";
  if (hint.kind === "route") {
    url = `${apiBase}/v1/chat/routes/${encodeURIComponent(String(hint.id))}/delivered`;
  } else if (hint.kind === "room") {
    url = `${apiBase}/v1/chats/rooms/${hint.id}/delivered`;
  } else {
    url = `${apiBase}/v1/salary/${hint.id}/chat/delivered`;
  }
  const ctrl = new AbortController();
  const timer = globalThis.setTimeout(() => ctrl.abort(), 12_000);
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ last_message_id: hint.messageId }),
      signal: ctrl.signal
    });
    return response.ok;
  } catch {
    return false;
  } finally {
    globalThis.clearTimeout(timer);
  }
}
