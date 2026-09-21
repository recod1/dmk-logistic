<script setup lang="ts">
import { computed } from "vue";

import MapsAddressLink from "./MapsAddressLink.vue";
import MapsCoordsLink from "./MapsCoordsLink.vue";
import {
  canRevertPointStatus,
  isPointDone,
  nextStatus,
  routeStatusLabel,
  statusLabel
} from "../status";
import type { RouteDto } from "../types";

const props = defineProps<{
  route: RouteDto;
  activeRouteId: string | null;
  syncing: boolean;
  canAcceptRoute: boolean;
  unreadChatCount?: number;
  logisticsContacts?: Array<{ name: string; phone: string }>;
}>();

const emit = defineEmits<{
  back: [];
  advancePoint: [pointId: number];
  revertPoint: [pointId: number];
  acceptRoute: [];
  openChat: [routeId: string];
}>();

const firstIncompletePoint = computed(
  () => props.route.points.find((point) => !isPointDone(point.status)) ?? null
);

const isAcceptedCurrentRoute = computed(
  () => props.route.status === "process" && props.route.id === props.activeRouteId
);

async function copyToClipboard(value: string): Promise<void> {
  const text = value.trim();
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    } catch {
      // ignore
    }
  }
}

function splitPhones(raw: string): string[] {
  const cleaned = raw.replace(/[()]/g, " ");
  const tokens = cleaned
    .split(/[\n,;]+/g)
    .map((x) => x.trim())
    .filter(Boolean);
  const result: string[] = [];
  for (const t of tokens) {
    // keep digits/+ only
    const num = t.replace(/[^+\d]/g, "");
    if (num.length >= 5) {
      result.push(num);
    }
  }
  return Array.from(new Set(result));
}

const dispatcherPhones = computed(() => splitPhones(props.route.dispatcher_contacts || ""));

const logisticsContacts = computed(() => {
  const fromSettings = (props.logisticsContacts ?? []).filter((item) => (item.name || "").trim() && (item.phone || "").trim());
  if (fromSettings.length) {
    return fromSettings;
  }
  return (props.route.logistics_contacts ?? []).filter((item) => (item.name || "").trim() && (item.phone || "").trim());
});

function phoneToTel(phoneRaw: string): string {
  return phoneRaw.replace(/[^+\d]/g, "");
}

function timeSourceLabel(value?: string | null): string {
  if (value === "manual") return " (вручную)";
  if (value === "device") return " (устройство)";
  return "";
}

function odoSourceLabel(value?: string | null): string {
  if (value === "wialon") return " (Wialon)";
  if (value === "manual") return " (вручную)";
  return "";
}

function stageLabel(stage: string): string {
  const labels: Record<string, string> = {
    accepted: "Выехал на точку",
    registration: "Регистрация",
    load: "На воротах",
    docs: "Забрал документы"
  };
  return labels[stage] ?? stage;
}

function actionLabel(status: string): string {
  if (status === "new") {
    return "Выехал на точку";
  }
  if (status === "process") {
    return "Зарегистрировался";
  }
  if (status === "registration") {
    return "Поставил на ворота";
  }
  if (status === "load") {
    return "Забрал документы";
  }
  return "Завершено";
}

function canAdvancePoint(pointId: number): boolean {
  const point = props.route.points.find((item) => item.id === pointId);
  if (!point) {
    return false;
  }
  return !isPointDone(point.status) && props.route.status === "process";
}

function showRevert(pointId: number): boolean {
  const point = props.route.points.find((item) => item.id === pointId);
  if (!point) {
    return false;
  }
  return isAcceptedCurrentRoute.value && canRevertPointStatus(point.status);
}
</script>

<template>
  <section class="details-wrap">
    <header class="head-row">
      <button class="ghost" type="button" @click="emit('back')">← Назад</button>
    </header>
    <h1 class="route-title">Рейс #{{ route.id }}</h1>

    <div class="scroll-area">
      <article class="card facts">
        <div class="kv">
          <span class="k">Статус рейса</span>
          <span class="v">{{ routeStatusLabel(route.status) }}</span>
        </div>
        <div class="kv">
          <span class="k">ТС</span>
          <span class="v">
            <button v-if="route.number_auto" class="copy" type="button" @click="copyToClipboard(route.number_auto)">{{ route.number_auto }}</button>
            <span v-else>—</span>
          </span>
        </div>
        <div class="kv">
          <span class="k">Прицеп</span>
          <span class="v">
            <button
              v-if="route.trailer_number"
              class="copy"
              type="button"
              @click="copyToClipboard(route.trailer_number)"
            >
              {{ route.trailer_number }}
            </button>
            <span v-else>—</span>
          </span>
        </div>
        <div class="kv">
          <span class="k">Температура</span>
          <span class="v">{{ route.temperature || "—" }}</span>
        </div>
        <div class="kv">
          <span class="k">Диспетчер</span>
          <span class="v">
            <span v-if="route.dispatcher_contacts" class="contacts">
              <a
                v-for="phone in dispatcherPhones"
                :key="phone"
                class="tel"
                :href="`tel:${phone}`"
                @click.stop
              >
                {{ phone }}
              </a>
            </span>
            <span v-else>—</span>
          </span>
        </div>
        <div class="kv">
          <span class="k">Контакты логистов</span>
          <span class="v">
            <span v-if="logisticsContacts.length" class="contacts">
              <a
                v-for="c in logisticsContacts"
                :key="`${c.name}-${c.phone}`"
                class="tel tel-contact"
                :href="`tel:${phoneToTel(c.phone)}`"
                @click.stop
              >
                <span class="tel-name">{{ c.name }}</span>
                <span class="tel-phone">{{ c.phone }}</span>
              </a>
            </span>
            <span v-else>—</span>
          </span>
        </div>
        <p v-if="!isAcceptedCurrentRoute && route.status === 'process'" class="note">
          Изменение статусов доступно только для принятого текущего рейса.
        </p>
        <button class="ghost wide chat-btn" type="button" @click="emit('openChat', route.id)">
          Открыть чат рейса
          <span v-if="(unreadChatCount ?? 0) > 0" class="chat-badge" aria-label="Новые сообщения" />
        </button>
      </article>

      <article class="card">
        <h2>Точки</h2>
        <div class="points">
          <div v-for="point in route.points" :key="point.id" class="point-card">
            <div class="row">
              <strong>{{ point.type_point === "unloading" ? "Выгрузка" : "Загрузка" }}</strong>
              <span class="chip">{{ statusLabel(point.status) }}</span>
            </div>
            <p v-if="point.place_point" class="addr">
              <MapsAddressLink :address="point.place_point" />
            </p>
            <small>{{ point.date_point }} {{ point.point_time || "" }}</small>
            <div class="stage-scroll">
              <table class="stage-table">
                <thead>
                  <tr>
                    <th>Этап</th>
                    <th>Время</th>
                    <th>Одометр</th>
                    <th>Координаты</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>{{ stageLabel("accepted") }}</td>
                    <td>{{ point.departure_time || point.time_accepted || "—" }}{{ timeSourceLabel(point.departure_time_source) }}</td>
                    <td>{{ point.departure_odometer || "—" }}{{ odoSourceLabel(point.departure_odometer_source) }}</td>
                    <td>
                      <MapsCoordsLink :lat="point.departure_coordinates?.lat" :lng="point.departure_coordinates?.lng" />
                    </td>
                  </tr>
                  <tr>
                    <td>{{ stageLabel("registration") }}</td>
                    <td>{{ point.registration_time || point.time_registration || "—" }}{{ timeSourceLabel(point.registration_time_source) }}</td>
                    <td>{{ point.registration_odometer || "—" }}{{ odoSourceLabel(point.registration_odometer_source) }}</td>
                    <td>
                      <MapsCoordsLink :lat="point.registration_coordinates?.lat" :lng="point.registration_coordinates?.lng" />
                    </td>
                  </tr>
                  <tr>
                    <td>{{ stageLabel("load") }}</td>
                    <td>{{ point.gate_time || point.time_put_on_gate || "—" }}{{ timeSourceLabel(point.gate_time_source) }}</td>
                    <td>{{ point.gate_odometer || "—" }}{{ odoSourceLabel(point.gate_odometer_source) }}</td>
                    <td>
                      <MapsCoordsLink :lat="point.gate_coordinates?.lat" :lng="point.gate_coordinates?.lng" />
                    </td>
                  </tr>
                  <tr>
                    <td>{{ stageLabel("docs") }}</td>
                    <td>{{ point.docs_time || point.time_docs || "—" }}{{ timeSourceLabel(point.docs_time_source) }}</td>
                    <td>{{ point.docs_odometer || "—" }}{{ odoSourceLabel(point.docs_odometer_source) }}</td>
                    <td>
                      <MapsCoordsLink :lat="point.docs_coordinates?.lat" :lng="point.docs_coordinates?.lng" />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </article>
    </div>

    <footer class="dock">
      <button
        v-if="canAcceptRoute"
        type="button"
        class="primary wide"
        @click="emit('acceptRoute')"
      >
        Принять рейс
      </button>

      <template v-if="isAcceptedCurrentRoute && firstIncompletePoint">
        <p v-if="nextStatus(firstIncompletePoint.status)" class="dock-hint">
          Текущая точка: этап «{{ statusLabel(firstIncompletePoint.status) }}»
        </p>
        <div class="dock-actions">
          <button
            v-if="canAdvancePoint(firstIncompletePoint.id)"
            type="button"
            class="primary wide"
            @click="emit('advancePoint', firstIncompletePoint.id)"
          >
            {{ actionLabel(firstIncompletePoint.status) }}
          </button>
          <button
            v-if="showRevert(firstIncompletePoint.id)"
            type="button"
            class="ghost wide"
            @click="emit('revertPoint', firstIncompletePoint.id)"
          >
            Вернуть предыдущий статус
          </button>
        </div>
      </template>
    </footer>
  </section>
</template>

<style scoped>
.details-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
  min-height: 0;
  width: 100%;
  max-width: 800px;
  margin: 0 auto;
}
.route-title {
  margin: 0;
  font-size: 1.15rem;
  line-height: 1.25;
  overflow-wrap: anywhere;
  letter-spacing: -0.02em;
}
.head-row {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 0.5rem;
}
.scroll-area {
  flex: 1;
  display: grid;
  gap: 0.75rem;
  min-height: 0;
}
.card {
  border: 1px solid var(--border);
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.92);
  padding: 0.8rem 0.95rem;
  box-shadow: var(--shadow-sm);
}
.facts {
  display: grid;
  gap: 0.55rem;
}
.card h2 {
  margin: 0 0 0.5rem;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-label);
}
.points {
  display: grid;
  gap: 0.55rem;
}
.point-card {
  border: 1px solid var(--border);
  border-radius: 14px;
  background: #111827;
  padding: 0.7rem;
  display: grid;
  gap: 0.35rem;
}
.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
.chip {
  border-radius: 999px;
  background: var(--chip);
  padding: 0.14rem 0.55rem;
  font-size: 0.78rem;
}
.stage-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  margin-top: 0.2rem;
}
.stage-table {
  width: 100%;
  min-width: 420px;
  border-collapse: collapse;
}
.stage-table th,
.stage-table td {
  padding: 0.42rem 0.4rem;
  border-bottom: 1px solid #243043;
  text-align: left;
  vertical-align: top;
}
.stage-table th {
  font-size: 0.7rem;
  font-weight: 650;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-label);
}
.stage-table td {
  color: var(--text-body);
  font-size: 0.82rem;
}
.point-card small {
  color: var(--text-label);
  font-size: 0.8rem;
}
.point-card strong {
  color: var(--text-heading);
}
.addr {
  margin: 0;
}
.maps-link {
  color: var(--accent);
  text-decoration: none;
  border-bottom: 1px solid rgba(56, 189, 248, 0.35);
  word-break: break-word;
}
p,
small {
  margin: 0;
}
.dock {
  position: sticky;
  bottom: 0;
  padding: 0.65rem 0 0.4rem;
  margin-top: auto;
  background: linear-gradient(180deg, transparent, #020617 35%);
  display: grid;
  gap: 0.5rem;
}
.dock-hint {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.86rem;
}
.dock-actions {
  display: grid;
  gap: 0.4rem;
}
.primary.wide,
.ghost.wide {
  width: 100%;
  min-height: 46px;
}
.chat-btn {
  position: relative;
}
.chat-badge {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 12px;
  height: 12px;
  border-radius: 999px;
  background: var(--danger);
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.2);
  animation: pulse-dot 1.8s ease-in-out infinite;
}
.primary {
  border: none;
  border-radius: 12px;
  background: linear-gradient(180deg, #3b82f6, #2563eb);
  color: #fff;
  padding: 0.55rem 0.78rem;
  font-weight: 650;
}
.ghost {
  border: 1px solid #78350f;
  border-radius: 12px;
  background: #451a03;
  color: #fed7aa;
  padding: 0.45rem 0.62rem;
}
.note {
  margin: 0.35rem 0 0;
  color: var(--text-muted);
  font-size: 0.88rem;
}
.copy {
  width: auto;
  border: 1px solid var(--border-strong);
  border-radius: 10px;
  background: transparent;
  color: #bfdbfe;
  padding: 0.25rem 0.5rem;
  font: inherit;
  text-align: left;
}
.contacts {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-right: 0.45rem;
}
.tel {
  border: 1px solid var(--border-strong);
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
  color: #a7f3d0;
  text-decoration: none;
}
.tel-contact {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  color: #d1fae5;
}
.tel-name {
  color: #86efac;
  font-weight: 600;
}
.tel-phone {
  color: #a7f3d0;
}
</style>
