<script setup lang="ts">
import { computed } from "vue";

import FactTimeCell from "./FactTimeCell.vue";
import MapsAddressLink from "./MapsAddressLink.vue";
import MapsCoordsLink from "./MapsCoordsLink.vue";
import PointDocLinks from "./PointDocLinks.vue";
import { liveRouteElapsedLabel, routeAnalyticsView } from "../routeAnalytics";
import { useLiveNow } from "../liveNow";
import { stageDeltasForPoint } from "../stageDeltas";
import {
  canRevertPointStatus,
  isPointDone,
  nextStatus,
  routeStatusLabel,
  statusLabel
} from "../status";
import { lateKindClass, lateReasonLines, pointLateKind } from "../lateArrival";
import { plannedScheduleDisplay } from "../plannedTime";
import { RETURN_WARNING, type RouteIncident } from "../routeIncidents";
import type { RouteDto } from "../types";

const props = defineProps<{
  route: RouteDto;
  activeRouteId: string | null;
  syncing: boolean;
  canAcceptRoute: boolean;
  unreadChatCount?: number;
  logisticsContacts?: Array<{ name: string; phone: string }>;
  incidents?: RouteIncident[];
  authToken?: string;
}>();

const emit = defineEmits<{
  back: [];
  advancePoint: [pointId: number];
  revertPoint: [pointId: number];
  acceptRoute: [];
  openChat: [routeId: string];
  reportProblem: [];
  followUp: [incident: RouteIncident];
  returnStage: [incident: RouteIncident];
}>();

const firstIncompletePoint = computed(
  () => (props.route.points || []).find((point) => !isPointDone(point.status)) ?? null
);

const nowMs = useLiveNow();
const routeAnalytics = computed(() => routeAnalyticsView(props.route.points));
const liveRouteTime = computed(() =>
  liveRouteElapsedLabel({
    points: props.route.points,
    status: props.route.status,
    acceptedAt: props.route.accepted_at,
    nowMs: nowMs.value
  })
);

const isAcceptedCurrentRoute = computed(
  () => props.route.status === "process" && props.route.id === props.activeRouteId
);

const openIncidents = computed(() => (props.incidents || []).filter((item) => item.status === "open"));

function pointHasProblem(pointId: number): boolean {
  return (props.incidents || []).some((item) => item.status === "open" && item.point_id === pointId);
}

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
const logistContactText = computed(() => (props.route.logist_contacts || "").trim());
const logistPhones = computed(() => splitPhones(logistContactText.value));

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
  const point = (props.route.points || []).find((item) => item.id === pointId);
  if (!point) {
    return false;
  }
  return !isPointDone(point.status) && props.route.status === "process";
}

function managerNames(point: RouteDto["points"][number]): string {
  const edits = point.manual_edits;
  if (!edits) return "";
  const names = new Set(
    Object.values(edits)
      .map((meta) => (meta.full_name || meta.login || "").trim())
      .filter(Boolean)
  );
  return names.size ? [...names].join(", ") : "";
}

function showRevert(pointId: number): boolean {
  const point = (props.route.points || []).find((item) => item.id === pointId);
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
          <span class="k">Время рейса</span>
          <span class="v live-time">{{ liveRouteTime }}</span>
        </div>
        <div class="kv">
          <span class="k">Общее время</span>
          <span class="v">{{ routeAnalytics.totalTime }}</span>
        </div>
        <div class="kv">
          <span class="k">Общий пробег</span>
          <span class="v">{{ routeAnalytics.totalKm }}</span>
        </div>
        <div class="kv">
          <span class="k">От регистрации до документов</span>
          <span class="v">{{ routeAnalytics.workTime }} · {{ routeAnalytics.workKm }}</span>
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
          <span class="k">Контакты диспетчера</span>
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
        <div class="kv kv-contacts">
          <span class="k">Контакты логиста</span>
          <span class="v">
            <span v-if="logistContactText" class="contacts">
              <a
                v-for="phone in logistPhones"
                :key="phone"
                class="tel"
                :href="`tel:${phone}`"
                @click.stop
              >
                {{ phone }}
              </a>
              <span v-if="!logistPhones.length">{{ logistContactText }}</span>
            </span>
            <span v-else-if="logisticsContacts.length" class="contacts">
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
        <p v-if="route.driver_lat != null && route.driver_lng != null" class="loc">
          Моя точка:
          <MapsCoordsLink :lat="route.driver_lat" :lng="route.driver_lng" />
        </p>
      </article>

      <article class="card">
        <h2>Точки</h2>
        <div class="points">
          <div v-for="point in route.points" :key="point.id" class="point-card" :class="[lateKindClass(pointLateKind(point)), { 'has-problem': pointHasProblem(point.id) }]">
            <div class="row">
              <strong>{{ point.type_point === "unloading" ? "Выгрузка" : "Загрузка" }}</strong>
              <span class="chip">{{ statusLabel(point.status) }}</span>
            </div>
            <p v-if="managerNames(point)" class="manager-note">Изменения менеджера: {{ managerNames(point) }}</p>
            <p v-if="point.point_name" class="org">{{ point.point_name }}</p>
            <p v-if="point.place_point" class="addr">
              <MapsAddressLink :address="point.place_point" />
            </p>
            <small>{{ plannedScheduleDisplay(point.date_point, point.point_time) }}</small>
            <p v-if="point.estimated_arrival" class="eta">Ориентировочное прибытие: {{ point.estimated_arrival }}</p>
            <div v-if="lateReasonLines(point.late_reason).length" class="late-reason">
              <p v-for="(line, idx) in lateReasonLines(point.late_reason)" :key="idx">{{ line }}</p>
            </div>
            <PointDocLinks
              v-if="authToken && point.docs_images?.length"
              :token="authToken"
              :images="point.docs_images"
            />
            <PointDocLinks
              v-if="authToken && point.return_images?.length"
              :token="authToken"
              :images="point.return_images"
              label="Фото возврата"
            />
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
                    <td>
                      <FactTimeCell
                        :time="point.departure_time || point.time_accepted"
                        :source="point.departure_time_source"
                        :pressed-at="point.departure_pressed_at"
                      />
                    </td>
                    <td>{{ point.departure_odometer || "—" }}{{ odoSourceLabel(point.departure_odometer_source) }}</td>
                    <td>
                      <MapsCoordsLink :lat="point.departure_coordinates?.lat" :lng="point.departure_coordinates?.lng" />
                    </td>
                  </tr>
                  <tr>
                    <td>{{ stageLabel("registration") }}</td>
                    <td>
                      <FactTimeCell
                        :time="point.registration_time || point.time_registration"
                        :source="point.registration_time_source"
                        :pressed-at="point.registration_pressed_at"
                      />
                    </td>
                    <td>{{ point.registration_odometer || "—" }}{{ odoSourceLabel(point.registration_odometer_source) }}</td>
                    <td>
                      <MapsCoordsLink :lat="point.registration_coordinates?.lat" :lng="point.registration_coordinates?.lng" />
                    </td>
                  </tr>
                  <tr>
                    <td>{{ stageLabel("load") }}</td>
                    <td>
                      <FactTimeCell
                        :time="point.gate_time || point.time_put_on_gate"
                        :source="point.gate_time_source"
                        :pressed-at="point.gate_pressed_at"
                      />
                    </td>
                    <td>{{ point.gate_odometer || "—" }}{{ odoSourceLabel(point.gate_odometer_source) }}</td>
                    <td>
                      <MapsCoordsLink :lat="point.gate_coordinates?.lat" :lng="point.gate_coordinates?.lng" />
                    </td>
                  </tr>
                  <tr>
                    <td>{{ stageLabel("docs") }}</td>
                    <td>
                      <FactTimeCell
                        :time="point.docs_time || point.time_docs"
                        :source="point.docs_time_source"
                        :pressed-at="point.docs_pressed_at"
                      />
                    </td>
                    <td>{{ point.docs_odometer || "—" }}{{ odoSourceLabel(point.docs_odometer_source) }}</td>
                    <td>
                      <MapsCoordsLink :lat="point.docs_coordinates?.lat" :lng="point.docs_coordinates?.lng" />
                    </td>
                  </tr>
                  <tr v-if="stageDeltasForPoint(point).registration">
                    <td colspan="4" class="delta">{{ stageDeltasForPoint(point).registration }}</td>
                  </tr>
                  <tr v-if="stageDeltasForPoint(point).gate">
                    <td colspan="4" class="delta">{{ stageDeltasForPoint(point).gate }}</td>
                  </tr>
                  <tr v-if="stageDeltasForPoint(point).docs">
                    <td colspan="4" class="delta">{{ stageDeltasForPoint(point).docs }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </article>

      <article v-if="openIncidents.length" class="card">
        <h2>Открытые проблемы</h2>
        <div v-for="item in openIncidents" :key="item.id" class="incident">
          <strong>{{ item.kind_label }}</strong>
          <p v-if="item.comment" class="note">{{ item.comment }}</p>
          <p v-if="item.cargo_name || item.quantity" class="note">
            {{ [item.cargo_name, item.quantity].filter(Boolean).join(" · ") }}
          </p>
          <p v-if="item.authorized_by" class="note">Разрешил: {{ item.authorized_by }}</p>
          <p v-if="item.kind === 'return' && item.return_warning" class="warn">{{ RETURN_WARNING }}</p>
          <p v-if="item.return_stage_label" class="note">Этап: {{ item.return_stage_label }}</p>
          <PointDocLinks
            v-if="authToken && item.images?.length"
            :token="authToken"
            :images="item.images"
            label="Фото возврата"
          />
          <button
            v-if="item.follow_up_label"
            class="secondary"
            type="button"
            @click="emit('followUp', item)"
          >
            {{ item.follow_up_label }}
          </button>
          <button
            v-if="item.kind === 'return' && item.next_return_stage_label"
            class="primary"
            type="button"
            @click="emit('returnStage', item)"
          >
            {{ item.next_return_stage_label }}
          </button>
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
          <div class="status-row">
            <button
              v-if="canAdvancePoint(firstIncompletePoint.id)"
              type="button"
              class="primary grow"
              @click="emit('advancePoint', firstIncompletePoint.id)"
            >
              {{ actionLabel(firstIncompletePoint.status) }}
            </button>
            <button class="problem-mini" type="button" @click="emit('reportProblem')">Проблема</button>
          </div>
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
@import "../lateHighlight.css";
.details-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
  min-height: 0;
  min-width: 0;
  width: 100%;
  max-width: min(800px, 100%);
  margin: 0 auto;
  overflow-x: hidden;
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
.live-time {
  font-variant-numeric: tabular-nums;
  color: #86efac;
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
  min-width: 0;
  max-width: 100%;
  overflow-wrap: anywhere;
}
.late-reason {
  margin: 0.2rem 0 0;
  display: grid;
  gap: 0.2rem;
  color: #fecaca;
  font-size: 0.86rem;
}
.late-reason p {
  margin: 0;
  white-space: pre-wrap;
}
.manager-note {
  margin: 0;
  color: #fde68a;
  font-size: 0.8rem;
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
  max-width: 100%;
}
.stage-table {
  width: 100%;
  min-width: 0;
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
.org {
  margin: 0.2rem 0 0;
  font-weight: 600;
}
.eta {
  margin: 0.25rem 0 0;
  color: var(--text-muted);
  font-size: 0.86rem;
}
.delta {
  color: #93c5fd;
  font-size: 0.78rem;
  overflow-wrap: anywhere;
}
.loc {
  margin: 0.4rem 0 0;
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
.status-row {
  display: flex;
  align-items: stretch;
  gap: 0.45rem;
}
.primary.grow {
  flex: 1 1 auto;
}
.problem-mini {
  flex: 0 0 auto;
  min-width: 4.4rem;
  padding: 0 0.55rem;
  border: none;
  border-radius: 12px;
  background: #b91c1c;
  color: #fff;
  font-size: 0.78rem;
  font-weight: 700;
}
.primary.wide,
.ghost.wide,
.primary.grow {
  min-height: 46px;
}
.primary.wide,
.ghost.wide {
  width: 100%;
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
.secondary.wide,
.secondary {
  border: 1px solid var(--border-strong);
  border-radius: 12px;
  background: var(--surface);
  color: #dbeafe;
  padding: 0.5rem 0.75rem;
  margin-top: 0.4rem;
}
.incident {
  display: grid;
  gap: 0.35rem;
  margin-top: 0.45rem;
}
.warn {
  margin: 0;
  color: #fecaca;
  font-weight: 650;
  line-height: 1.35;
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
.kv-contacts {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 0.45rem;
  grid-template-columns: unset;
}
.kv-contacts .k {
  flex: 0 0 auto;
  white-space: nowrap;
  padding-top: 0;
}
.kv-contacts :deep(.v),
.kv-contacts .v {
  flex: 1 1 auto;
  min-width: 0;
  overflow-x: auto;
  overflow-wrap: normal;
  word-break: keep-all;
  -webkit-overflow-scrolling: touch;
}
.contacts {
  display: inline-flex;
  flex-wrap: nowrap;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.35rem;
  margin-right: 0.45rem;
  max-width: 100%;
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
  flex-wrap: nowrap;
  align-items: center;
  gap: 0.4rem;
  color: #d1fae5;
  white-space: nowrap;
  flex-shrink: 0;
  font-size: clamp(0.72rem, 3.5vw, 0.85rem);
}
.tel-name,
.tel-phone {
  white-space: nowrap;
  flex-shrink: 0;
}
.tel-name {
  color: #86efac;
  font-weight: 600;
}
.tel-phone {
  color: #a7f3d0;
}
</style>
