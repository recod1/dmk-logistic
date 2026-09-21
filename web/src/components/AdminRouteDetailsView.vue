<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";

import MapsAddressLink from "./MapsAddressLink.vue";
import MapsCoordsLink from "./MapsCoordsLink.vue";
import PointDocLinks from "./PointDocLinks.vue";
import { displayRuToDatetimeLocal, fromDatetimeLocalToIso } from "../datetimeLocal";
import { listPointStatusLabel } from "../status";
import type { AdminRoute, AdminRoutePointPayload, DriverOption, ManualEditMeta, RouteWorkflowStatus } from "../types";

type AdminRoutePoint = NonNullable<AdminRoute["points"]>[number];

type PointStageEdit = {
  type_point: string;
  place_point: string;
  date_point: string;
  point_time: string;
  point_name: string;
  point_contacts: string;
  point_note: string;
  departure_time: string;
  departure_odometer: string;
  departure_lat: string;
  departure_lng: string;
  registration_time: string;
  registration_odometer: string;
  registration_lat: string;
  registration_lng: string;
  gate_time: string;
  gate_odometer: string;
  gate_lat: string;
  gate_lng: string;
  docs_time: string;
  docs_odometer: string;
  docs_lat: string;
  docs_lng: string;
  status: string;
};

type PointForm = {
  id?: number;
  type_point: string;
  place_point: string;
  date_point: string;
  point_time: string;
};

const props = defineProps<{
  route: AdminRoute;
  drivers: DriverOption[];
  loading: boolean;
  authToken: string;
  unreadChatCount?: number;
  error?: string;
}>();

const emit = defineEmits<{
  back: [];
  assignDriver: [routeId: string, driverUserId: number];
  cancelRoute: [routeId: string];
  deleteRoute: [routeId: string];
  updateRoute: [
    routeId: string,
    payload: {
      number_auto?: string;
      temperature?: string;
      dispatcher_contacts?: string;
      registration_number?: string;
      trailer_number?: string;
      points?: AdminRoutePointPayload[];
    }
  ];
  openChat: [routeId: string];
  updatePoint: [pointId: number, payload: Record<string, unknown>];
}>();

const showReassign = ref(false);
const showEdit = ref(false);
const reassignDriverId = ref(0);
const editingPointId = ref<number | null>(null);

const editForm = reactive({
  number_auto: "",
  temperature: "",
  dispatcher_contacts: "",
  registration_number: "",
  trailer_number: "",
  points: [] as PointForm[]
});

function statusLabel(status: RouteWorkflowStatus): string {
  const labels: Record<RouteWorkflowStatus, string> = {
    new: "Не принят",
    process: "В процессе",
    success: "Завершён",
    cancelled: "Отменён"
  };
  return labels[status] ?? status;
}

function upperOnly(value: string): string {
  return (value || "").toUpperCase();
}

function routeStatusWithCurrentPoint(route: AdminRoute): string {
  const base = statusLabel(route.status);
  const current = (route.points || []).find((point) => point.status !== "docs" && point.status !== "success");
  if (!current) {
    return base;
  }
  const address = (current.place_point || "").trim();
  const stage = pointStatusLabel(current.status);
  return `${base} · ${stage}${address ? ` · ${address}` : ""}`;
}

function pointTypeLabel(value: string): string {
  return value === "unloading" ? "Выгрузка" : "Загрузка";
}

function normalizePointStageLabel(stage: string): string {
  const labels: Record<string, string> = {
    accepted: "Выехал на точку",
    registration: "Регистрация",
    load: "На воротах",
    docs: "Забрал документы"
  };
  return labels[stage] ?? stage;
}

function odoSourceLabel(value?: string | null): string {
  if (value === "wialon") return " (Wialon)";
  if (value === "manual") return " (вручную)";
  return "";
}

function pointStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    new: "Новая",
    process: "Выехал на точку",
    registration: "Зарегистрировался",
    load: "На воротах",
    docs: "Забрал документы",
    success: "Забрал документы"
  };
  return labels[status] ?? status;
}

function canCancel(status: RouteWorkflowStatus): boolean {
  return status === "new" || status === "process";
}

function phoneReceiptLabel(route: AdminRoute): string {
  if (!route.driver?.id) {
    return "—";
  }
  return route.driver_received_at ? "Получен" : "Не получен";
}

function phoneReceiptHint(route: AdminRoute): string {
  if (!route.driver_received_at) {
    return "Водитель ещё не получил рейс на телефон";
  }
  try {
    return `Скачан на телефон: ${new Date(route.driver_received_at).toLocaleString()}`;
  } catch {
    return "Рейс скачан приложением на телефоне водителя";
  }
}

function makeEmptyPoint(): PointForm {
  return {
    type_point: "loading",
    place_point: "",
    date_point: "",
    point_time: ""
  };
}

function emptyPointStageEdit(): PointStageEdit {
  return {
    type_point: "loading",
    place_point: "",
    date_point: "",
    point_time: "",
    point_name: "",
    point_contacts: "",
    point_note: "",
    departure_time: "",
    departure_odometer: "",
    departure_lat: "",
    departure_lng: "",
    registration_time: "",
    registration_odometer: "",
    registration_lat: "",
    registration_lng: "",
    gate_time: "",
    gate_odometer: "",
    gate_lat: "",
    gate_lng: "",
    docs_time: "",
    docs_odometer: "",
    docs_lat: "",
    docs_lng: "",
    status: "new"
  };
}

const pointEdit = reactive<PointStageEdit>(emptyPointStageEdit());

function coordText(value?: number | null): string {
  return typeof value === "number" && Number.isFinite(value) ? String(value) : "";
}

function parseCoord(value: string): number | null {
  const trimmed = value.trim().replace(",", ".");
  if (!trimmed) {
    return null;
  }
  const num = Number(trimmed);
  return Number.isFinite(num) ? num : null;
}

function changedText(form: string, original?: string | null): string | undefined {
  const next = form.trim();
  const prev = (original || "").trim();
  return next === prev ? undefined : next;
}

function changedDate(form: string, original?: string | null): string | undefined {
  const next = form.trim();
  const prev = (original || "").trim();
  if (next === prev) {
    return undefined;
  }
  if (!next && prev && !/^\d{4}-\d{2}-\d{2}$/.test(prev)) {
    return undefined;
  }
  return next;
}

function changedTimeIso(formLocal: string, originalDisplay?: string | null): string | undefined {
  const next = formLocal.trim();
  const originalLocal = displayRuToDatetimeLocal(originalDisplay);
  if (!next) {
    if (!originalDisplay?.trim() || !originalLocal) {
      return undefined;
    }
    return "";
  }
  if (next === originalLocal) {
    return undefined;
  }
  return fromDatetimeLocalToIso(next);
}

function changedOdometer(form: string, original?: string | null): string | undefined {
  const next = form.trim();
  const prev = (original || "").trim();
  return next === prev ? undefined : next;
}

function changedCoords(
  latForm: string,
  lngForm: string,
  original?: { lat?: number | null; lng?: number | null } | null
): { lat: number | null; lng: number | null } | undefined {
  const lat = parseCoord(latForm);
  const lng = parseCoord(lngForm);
  const prevLat = typeof original?.lat === "number" && Number.isFinite(original.lat) ? original.lat : null;
  const prevLng = typeof original?.lng === "number" && Number.isFinite(original.lng) ? original.lng : null;
  if (lat === prevLat && lng === prevLng) {
    return undefined;
  }
  return { lat, lng };
}

function editHint(edits: Record<string, ManualEditMeta> | null | undefined, key: string): string {
  const meta = edits?.[key];
  if (!meta) {
    return "";
  }
  const name = (meta.full_name || meta.login || "").trim();
  return name ? `изменено: ${name}` : "";
}

function fillPointStageEdit(point: AdminRoutePoint): void {
  Object.assign(pointEdit, emptyPointStageEdit(), {
    type_point: point.type_point || "loading",
    place_point: point.place_point || "",
    date_point: point.date_point || "",
    point_time: point.point_time || "",
    point_name: point.point_name || "",
    point_contacts: point.point_contacts || "",
    point_note: point.point_note || "",
    departure_time: displayRuToDatetimeLocal(point.departure_time || point.time_accepted),
    departure_odometer: point.departure_odometer || "",
    departure_lat: coordText(point.departure_coordinates?.lat),
    departure_lng: coordText(point.departure_coordinates?.lng),
    registration_time: displayRuToDatetimeLocal(point.registration_time || point.time_registration),
    registration_odometer: point.registration_odometer || "",
    registration_lat: coordText(point.registration_coordinates?.lat),
    registration_lng: coordText(point.registration_coordinates?.lng),
    gate_time: displayRuToDatetimeLocal(point.gate_time || point.time_put_on_gate),
    gate_odometer: point.gate_odometer || "",
    gate_lat: coordText(point.gate_coordinates?.lat),
    gate_lng: coordText(point.gate_coordinates?.lng),
    docs_time: displayRuToDatetimeLocal(point.docs_time || point.time_docs),
    docs_odometer: point.docs_odometer || "",
    docs_lat: coordText(point.docs_coordinates?.lat),
    docs_lng: coordText(point.docs_coordinates?.lng),
    status: point.status === "success" ? "docs" : point.status || "new"
  });
}

function openPointEdit(point: AdminRoutePoint): void {
  editingPointId.value = point.id;
  fillPointStageEdit(point);
}

function closePointEdit(): void {
  editingPointId.value = null;
}

function submitPointEdit(point: AdminRoutePoint): void {
  const payload: Record<string, unknown> = {};
  const typePoint = changedText(pointEdit.type_point, point.type_point);
  const placePoint = changedText(pointEdit.place_point, point.place_point);
  const datePoint = changedDate(pointEdit.date_point, point.date_point);
  const pointName = changedText(pointEdit.point_name, point.point_name);
  const pointContacts = changedText(pointEdit.point_contacts, point.point_contacts);
  const pointTime = changedText(pointEdit.point_time, point.point_time);
  const pointNote = changedText(pointEdit.point_note, point.point_note);
  const departureTime = changedTimeIso(pointEdit.departure_time, point.departure_time || point.time_accepted);
  const departureOdometer = changedOdometer(pointEdit.departure_odometer, point.departure_odometer);
  const departureCoordinates = changedCoords(pointEdit.departure_lat, pointEdit.departure_lng, point.departure_coordinates);
  const registrationTime = changedTimeIso(pointEdit.registration_time, point.registration_time || point.time_registration);
  const registrationOdometer = changedOdometer(pointEdit.registration_odometer, point.registration_odometer);
  const registrationCoordinates = changedCoords(
    pointEdit.registration_lat,
    pointEdit.registration_lng,
    point.registration_coordinates
  );
  const gateTime = changedTimeIso(pointEdit.gate_time, point.gate_time || point.time_put_on_gate);
  const gateOdometer = changedOdometer(pointEdit.gate_odometer, point.gate_odometer);
  const gateCoordinates = changedCoords(pointEdit.gate_lat, pointEdit.gate_lng, point.gate_coordinates);
  const docsTime = changedTimeIso(pointEdit.docs_time, point.docs_time || point.time_docs);
  const docsOdometer = changedOdometer(pointEdit.docs_odometer, point.docs_odometer);
  const docsCoordinates = changedCoords(pointEdit.docs_lat, pointEdit.docs_lng, point.docs_coordinates);
  const nextStatus = (pointEdit.status || "").trim();
  const currentStatus = point.status === "success" ? "docs" : point.status;

  if (typePoint !== undefined) payload.type_point = typePoint;
  if (placePoint !== undefined) payload.place_point = placePoint;
  if (datePoint !== undefined) payload.date_point = datePoint;
  if (pointName !== undefined) payload.point_name = pointName;
  if (pointContacts !== undefined) payload.point_contacts = pointContacts;
  if (pointTime !== undefined) payload.point_time = pointTime;
  if (pointNote !== undefined) payload.point_note = pointNote;
  if (departureTime !== undefined) payload.departure_time = departureTime;
  if (departureOdometer !== undefined) payload.departure_odometer = departureOdometer;
  if (departureCoordinates) payload.departure_coordinates = departureCoordinates;
  if (registrationTime !== undefined) payload.registration_time = registrationTime;
  if (registrationOdometer !== undefined) payload.registration_odometer = registrationOdometer;
  if (registrationCoordinates) payload.registration_coordinates = registrationCoordinates;
  if (gateTime !== undefined) payload.gate_time = gateTime;
  if (gateOdometer !== undefined) payload.gate_odometer = gateOdometer;
  if (gateCoordinates) payload.gate_coordinates = gateCoordinates;
  if (docsTime !== undefined) payload.docs_time = docsTime;
  if (docsOdometer !== undefined) payload.docs_odometer = docsOdometer;
  if (docsCoordinates) payload.docs_coordinates = docsCoordinates;
  if (nextStatus && nextStatus !== currentStatus) payload.status = nextStatus;

  if (!Object.keys(payload).length) {
    editingPointId.value = null;
    return;
  }
  emit("updatePoint", point.id, payload);
  editingPointId.value = null;
}

function toPointPayload(points: PointForm[]): AdminRoutePointPayload[] {
  return points.map((point, index) => ({
    id: point.id,
    type_point: point.type_point || "loading",
    place_point: point.place_point.trim(),
    date_point: point.date_point.trim(),
    point_name: "",
    point_contacts: "",
    point_time: point.point_time.trim(),
    point_note: "",
    order_index: index
  }));
}

watch(
  () => props.route,
  (route) => {
    editForm.number_auto = route.number_auto || "";
    editForm.temperature = route.temperature || "";
    editForm.dispatcher_contacts = route.dispatcher_contacts || "";
    editForm.registration_number = route.registration_number || "";
    editForm.trailer_number = route.trailer_number || "";
    editForm.points = (route.points || []).map((point) => ({
      id: point.id,
      type_point: point.type_point || "loading",
      place_point: point.place_point || "",
      date_point: point.date_point || "",
      point_time: point.point_time || ""
    }));
    reassignDriverId.value = route.driver?.id ?? 0;
    if (editingPointId.value != null) {
      const current = (route.points || []).find((item) => item.id === editingPointId.value);
      if (!current) {
        editingPointId.value = null;
      }
    }
  },
  { immediate: true }
);

const canAssign = computed(() => reassignDriverId.value > 0);

function openReassign(): void {
  showReassign.value = true;
}

function closeReassign(): void {
  showReassign.value = false;
}

function openEdit(): void {
  showEdit.value = true;
}

function closeEdit(): void {
  showEdit.value = false;
}

function addEditPoint(): void {
  editForm.points.push(makeEmptyPoint());
}

function removeEditPoint(index: number): void {
  editForm.points.splice(index, 1);
}

function submitEdit(): void {
  emit("updateRoute", props.route.id, {
    number_auto: editForm.number_auto.trim(),
    temperature: editForm.temperature.trim(),
    dispatcher_contacts: editForm.dispatcher_contacts.trim(),
    registration_number: editForm.registration_number.trim(),
    trailer_number: editForm.trailer_number.trim(),
    points: toPointPayload(editForm.points).filter((point) => point.place_point && point.date_point)
  });
}

function submitReassign(): void {
  if (!canAssign.value) {
    return;
  }
  emit("assignDriver", props.route.id, reassignDriverId.value);
}

function removeRoute(): void {
  if (!window.confirm(`Удалить рейс ${props.route.id}?`)) {
    return;
  }
  emit("deleteRoute", props.route.id);
}
</script>

<template>
  <section class="details-page">
    <section class="card details-card">
      <div class="head">
        <h2>Рейс {{ route.id }}</h2>
        <button class="ghost" @click="emit('back')">← Назад</button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>

      <div class="summary-grid">
        <div class="kv">
          <span class="k">N рейса</span>
          <span class="v">{{ route.id }}</span>
        </div>
        <div class="kv">
          <span class="k">Водитель</span>
          <span class="v">{{ route.driver?.full_name || route.driver?.login || "—" }}</span>
        </div>
        <div class="kv">
          <span class="k">ТС</span>
          <span class="v">{{ route.number_auto || "—" }}</span>
        </div>
        <div class="kv">
          <span class="k">Прицеп</span>
          <span class="v">{{ route.trailer_number || "—" }}</span>
        </div>
        <div class="kv">
          <span class="k">Статус</span>
          <span class="v">{{ routeStatusWithCurrentPoint(route) }}</span>
        </div>
        <div class="kv">
          <span class="k">На телефоне</span>
          <span
            class="v"
            :class="route.driver?.id && route.driver_received_at ? 'ok' : 'muted-value'"
            :title="phoneReceiptHint(route)"
          >
            {{ phoneReceiptLabel(route) }}
          </span>
        </div>
        <div class="kv">
          <span class="k">Температура</span>
          <span class="v">{{ route.temperature || "—" }}</span>
        </div>
        <div class="kv">
          <span class="k">Контакты диспетчера</span>
          <span class="v">{{ route.dispatcher_contacts || "—" }}</span>
        </div>
        <div class="kv">
          <span class="k">N регистрации</span>
          <span class="v">{{ route.registration_number || "—" }}</span>
        </div>
      </div>
      <section class="actions top-actions">
        <button class="secondary chat-btn" type="button" @click="emit('openChat', route.id)">
          Открыть чат рейса
          <span v-if="(unreadChatCount ?? 0) > 0" class="chat-badge" aria-label="Новые сообщения" />
        </button>
        <button class="secondary" v-if="!showEdit" :disabled="loading" type="button" @click="openEdit">Редактировать</button>
        <button class="secondary" v-if="!showReassign" :disabled="loading" type="button" @click="openReassign">
          Переназначить
        </button>
        <div v-if="showReassign" class="reassign-wrap">
          <select v-model.number="reassignDriverId">
            <option :value="0">Выберите водителя</option>
            <option v-for="driver in drivers" :key="driver.id" :value="driver.id">
              {{ driver.full_name || driver.login }}
            </option>
          </select>
          <button class="secondary" type="button" :disabled="loading || !canAssign" @click="submitReassign">Сохранить</button>
          <button class="ghost" type="button" @click="closeReassign">Отмена</button>
        </div>
        <button class="danger" type="button" :disabled="loading || !canCancel(route.status)" @click="emit('cancelRoute', route.id)">
          Отменить
        </button>
        <button class="danger soft" type="button" :disabled="loading" @click="removeRoute">Удалить рейс</button>
      </section>

      <section v-if="showEdit" class="edit-card">
        <h3>Редактирование рейса</h3>
        <div class="edit-grid">
          <label>
            Номер авто
            <input
              v-model="editForm.number_auto"
              class="upper"
              autocapitalize="characters"
              @input="(e) => (editForm.number_auto = upperOnly((e.target as HTMLInputElement).value))"
            />
          </label>
          <label>
            Температура
            <input v-model="editForm.temperature" />
          </label>
          <label>
            Контакты диспетчера
            <input v-model="editForm.dispatcher_contacts" />
          </label>
          <label>
            Номер регистрации
            <input v-model="editForm.registration_number" />
          </label>
          <label>
            Номер прицепа
            <input
              v-model="editForm.trailer_number"
              class="upper"
              autocapitalize="characters"
              @input="(e) => (editForm.trailer_number = upperOnly((e.target as HTMLInputElement).value))"
            />
          </label>
        </div>
        <div class="actions">
          <button class="secondary" :disabled="loading" @click="submitEdit">Сохранить изменения</button>
          <button class="ghost" @click="closeEdit">Отмена</button>
        </div>
      </section>

      <section v-if="showEdit" class="points-wrap">
        <div class="points-head">
          <h3>Точки</h3>
          <button class="secondary" @click="addEditPoint">Добавить точку</button>
        </div>
        <article v-for="(point, idx) in editForm.points" :key="`edit-${idx}`" class="point-card">
          <div class="point-top">
            <strong>{{ pointTypeLabel(point.type_point) }}</strong>
            <button class="danger soft" @click="removeEditPoint(idx)">Удалить</button>
          </div>
          <p class="muted">{{ point.date_point || "—" }} · {{ point.point_time || "—" }}</p>
          <p class="muted">{{ point.place_point || "—" }}</p>
          <div class="point-edit-grid">
            <label>
              Тип
              <select v-model="point.type_point">
                <option value="loading">Загрузка</option>
                <option value="unloading">Выгрузка</option>
              </select>
            </label>
            <label>
              Дата
              <input v-model="point.date_point" type="date" />
            </label>
            <label>
              Время
              <input v-model="point.point_time" type="time" step="60" />
            </label>
            <label>
              Адрес
              <input v-model="point.place_point" />
            </label>
          </div>
        </article>
      </section>

      <section class="points-wrap">
        <h3>Этапы по точкам</h3>
        <article v-for="point in route.points || []" :key="point.id" class="point-card">
          <div class="point-top">
            <strong>
              {{ pointTypeLabel(point.type_point) }}
              ·
              <MapsAddressLink v-if="point.place_point" :address="point.place_point" />
              <span v-else>Без адреса</span>
            </strong>
            <span class="status-chip">{{ pointStatusLabel(point.status) }}</span>
          </div>
          <p class="meta-line">{{ point.date_point || "—" }} · {{ point.point_time || "—" }}</p>
          <p v-if="point.point_name || point.point_contacts" class="meta-line">
            {{ point.point_name || "—" }}{{ point.point_contacts ? ` · ${point.point_contacts}` : "" }}
          </p>
          <div v-if="editingPointId !== point.id" class="actions">
            <button class="secondary" type="button" :disabled="loading" @click="openPointEdit(point)">
              Изменить точку
            </button>
          </div>
          <div v-if="editingPointId === point.id" class="point-full-edit">
            <div class="point-edit-grid">
              <label class="full">
                Статус точки
                <select v-model="pointEdit.status">
                  <option value="new">{{ listPointStatusLabel("new") }}</option>
                  <option value="process">{{ listPointStatusLabel("process") }}</option>
                  <option value="registration">{{ listPointStatusLabel("registration") }}</option>
                  <option value="load">{{ listPointStatusLabel("load") }}</option>
                  <option value="docs">{{ listPointStatusLabel("docs") }}</option>
                </select>
                <small class="edit-hint">Меняется только этим полем. Правка времени, одометра и координат статус не трогает.</small>
                <small v-if="editHint(point.manual_edits, 'status')" class="edit-hint">{{ editHint(point.manual_edits, 'status') }}</small>
              </label>
              <label>
                Тип
                <select v-model="pointEdit.type_point">
                  <option value="loading">Загрузка</option>
                  <option value="unloading">Выгрузка</option>
                </select>
                <small v-if="editHint(point.manual_edits, 'type_point')" class="edit-hint">{{ editHint(point.manual_edits, 'type_point') }}</small>
              </label>
              <label>
                Дата
                <input v-model="pointEdit.date_point" type="date" />
                <small v-if="editHint(point.manual_edits, 'date_point')" class="edit-hint">{{ editHint(point.manual_edits, 'date_point') }}</small>
              </label>
              <label>
                Время плана
                <input v-model="pointEdit.point_time" type="time" step="60" />
                <small v-if="editHint(point.manual_edits, 'point_time')" class="edit-hint">{{ editHint(point.manual_edits, 'point_time') }}</small>
              </label>
              <label class="full">
                Адрес
                <input v-model="pointEdit.place_point" />
                <small v-if="editHint(point.manual_edits, 'place_point')" class="edit-hint">{{ editHint(point.manual_edits, 'place_point') }}</small>
              </label>
              <label>
                Название
                <input v-model="pointEdit.point_name" />
                <small v-if="editHint(point.manual_edits, 'point_name')" class="edit-hint">{{ editHint(point.manual_edits, 'point_name') }}</small>
              </label>
              <label>
                Контакты
                <input v-model="pointEdit.point_contacts" />
                <small v-if="editHint(point.manual_edits, 'point_contacts')" class="edit-hint">{{ editHint(point.manual_edits, 'point_contacts') }}</small>
              </label>
              <label class="full">
                Примечание
                <input v-model="pointEdit.point_note" />
                <small v-if="editHint(point.manual_edits, 'point_note')" class="edit-hint">{{ editHint(point.manual_edits, 'point_note') }}</small>
              </label>
            </div>
            <h4>Этапы</h4>
            <div class="stage-edit-grid">
              <p class="stage-edit-title">Выехал на точку</p>
              <label>
                Время
                <input v-model="pointEdit.departure_time" type="datetime-local" />
                <small v-if="editHint(point.manual_edits, 'departure_time')" class="edit-hint">{{ editHint(point.manual_edits, 'departure_time') }}</small>
              </label>
              <label>
                Одометр
                <input v-model="pointEdit.departure_odometer" />
                <small v-if="editHint(point.manual_edits, 'departure_odometer')" class="edit-hint">{{ editHint(point.manual_edits, 'departure_odometer') }}</small>
              </label>
              <label>
                Широта
                <input v-model="pointEdit.departure_lat" inputmode="decimal" />
              </label>
              <label>
                Долгота
                <input v-model="pointEdit.departure_lng" inputmode="decimal" />
                <small v-if="editHint(point.manual_edits, 'departure_coordinates')" class="edit-hint">{{ editHint(point.manual_edits, 'departure_coordinates') }}</small>
              </label>

              <p class="stage-edit-title">Регистрация</p>
              <label>
                Время
                <input v-model="pointEdit.registration_time" type="datetime-local" />
                <small v-if="editHint(point.manual_edits, 'registration_time')" class="edit-hint">{{ editHint(point.manual_edits, 'registration_time') }}</small>
              </label>
              <label>
                Одометр
                <input v-model="pointEdit.registration_odometer" />
                <small v-if="editHint(point.manual_edits, 'registration_odometer')" class="edit-hint">{{ editHint(point.manual_edits, 'registration_odometer') }}</small>
              </label>
              <label>
                Широта
                <input v-model="pointEdit.registration_lat" inputmode="decimal" />
              </label>
              <label>
                Долгота
                <input v-model="pointEdit.registration_lng" inputmode="decimal" />
                <small v-if="editHint(point.manual_edits, 'registration_coordinates')" class="edit-hint">{{ editHint(point.manual_edits, 'registration_coordinates') }}</small>
              </label>

              <p class="stage-edit-title">На воротах</p>
              <label>
                Время
                <input v-model="pointEdit.gate_time" type="datetime-local" />
                <small v-if="editHint(point.manual_edits, 'gate_time')" class="edit-hint">{{ editHint(point.manual_edits, 'gate_time') }}</small>
              </label>
              <label>
                Одометр
                <input v-model="pointEdit.gate_odometer" />
                <small v-if="editHint(point.manual_edits, 'gate_odometer')" class="edit-hint">{{ editHint(point.manual_edits, 'gate_odometer') }}</small>
              </label>
              <label>
                Широта
                <input v-model="pointEdit.gate_lat" inputmode="decimal" />
              </label>
              <label>
                Долгота
                <input v-model="pointEdit.gate_lng" inputmode="decimal" />
                <small v-if="editHint(point.manual_edits, 'gate_coordinates')" class="edit-hint">{{ editHint(point.manual_edits, 'gate_coordinates') }}</small>
              </label>

              <p class="stage-edit-title">Забрал документы</p>
              <label>
                Время
                <input v-model="pointEdit.docs_time" type="datetime-local" />
                <small v-if="editHint(point.manual_edits, 'docs_time')" class="edit-hint">{{ editHint(point.manual_edits, 'docs_time') }}</small>
              </label>
              <label>
                Одометр
                <input v-model="pointEdit.docs_odometer" />
                <small v-if="editHint(point.manual_edits, 'docs_odometer')" class="edit-hint">{{ editHint(point.manual_edits, 'docs_odometer') }}</small>
              </label>
              <label>
                Широта
                <input v-model="pointEdit.docs_lat" inputmode="decimal" />
              </label>
              <label>
                Долгота
                <input v-model="pointEdit.docs_lng" inputmode="decimal" />
                <small v-if="editHint(point.manual_edits, 'docs_coordinates')" class="edit-hint">{{ editHint(point.manual_edits, 'docs_coordinates') }}</small>
              </label>
            </div>
            <div class="actions">
              <button
                class="secondary"
                type="button"
                :disabled="loading"
                @mousedown.prevent
                @click="submitPointEdit(point)"
              >
                Сохранить точку
              </button>
              <button class="ghost" type="button" @click="closePointEdit">Отмена</button>
            </div>
          </div>
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
                <td>{{ normalizePointStageLabel("accepted") }}</td>
                <td>
                  {{ point.departure_time || point.time_accepted || "—" }}
                  <small v-if="editHint(point.manual_edits, 'departure_time')" class="edit-hint">{{ editHint(point.manual_edits, 'departure_time') }}</small>
                </td>
                <td>
                  {{ point.departure_odometer || "—" }}{{ odoSourceLabel(point.departure_odometer_source) }}
                  <small v-if="editHint(point.manual_edits, 'departure_odometer')" class="edit-hint">{{ editHint(point.manual_edits, 'departure_odometer') }}</small>
                </td>
                <td>
                  <MapsCoordsLink :lat="point.departure_coordinates?.lat" :lng="point.departure_coordinates?.lng" />
                  <small v-if="editHint(point.manual_edits, 'departure_coordinates')" class="edit-hint">{{ editHint(point.manual_edits, 'departure_coordinates') }}</small>
                </td>
              </tr>
              <tr>
                <td>{{ normalizePointStageLabel("registration") }}</td>
                <td>
                  {{ point.registration_time || point.time_registration || "—" }}
                  <small v-if="editHint(point.manual_edits, 'registration_time')" class="edit-hint">{{ editHint(point.manual_edits, 'registration_time') }}</small>
                </td>
                <td>
                  {{ point.registration_odometer || "—" }}{{ odoSourceLabel(point.registration_odometer_source) }}
                  <small v-if="editHint(point.manual_edits, 'registration_odometer')" class="edit-hint">{{ editHint(point.manual_edits, 'registration_odometer') }}</small>
                </td>
                <td>
                  <MapsCoordsLink :lat="point.registration_coordinates?.lat" :lng="point.registration_coordinates?.lng" />
                  <small v-if="editHint(point.manual_edits, 'registration_coordinates')" class="edit-hint">{{ editHint(point.manual_edits, 'registration_coordinates') }}</small>
                </td>
              </tr>
              <tr>
                <td>{{ normalizePointStageLabel("load") }}</td>
                <td>
                  {{ point.gate_time || point.time_put_on_gate || "—" }}
                  <small v-if="editHint(point.manual_edits, 'gate_time')" class="edit-hint">{{ editHint(point.manual_edits, 'gate_time') }}</small>
                </td>
                <td>
                  {{ point.gate_odometer || "—" }}{{ odoSourceLabel(point.gate_odometer_source) }}
                  <small v-if="editHint(point.manual_edits, 'gate_odometer')" class="edit-hint">{{ editHint(point.manual_edits, 'gate_odometer') }}</small>
                </td>
                <td>
                  <MapsCoordsLink :lat="point.gate_coordinates?.lat" :lng="point.gate_coordinates?.lng" />
                  <small v-if="editHint(point.manual_edits, 'gate_coordinates')" class="edit-hint">{{ editHint(point.manual_edits, 'gate_coordinates') }}</small>
                </td>
              </tr>
              <tr>
                <td>{{ normalizePointStageLabel("docs") }}</td>
                <td>
                  {{ point.docs_time || point.time_docs || "—" }}
                  <small v-if="editHint(point.manual_edits, 'docs_time')" class="edit-hint">{{ editHint(point.manual_edits, 'docs_time') }}</small>
                </td>
                <td>
                  {{ point.docs_odometer || "—" }}{{ odoSourceLabel(point.docs_odometer_source) }}
                  <small v-if="editHint(point.manual_edits, 'docs_odometer')" class="edit-hint">{{ editHint(point.manual_edits, 'docs_odometer') }}</small>
                </td>
                <td>
                  <MapsCoordsLink :lat="point.docs_coordinates?.lat" :lng="point.docs_coordinates?.lng" />
                  <small v-if="editHint(point.manual_edits, 'docs_coordinates')" class="edit-hint">{{ editHint(point.manual_edits, 'docs_coordinates') }}</small>
                </td>
              </tr>
            </tbody>
          </table>
          </div>
          <PointDocLinks
            v-if="authToken && point.docs_images?.length"
            :token="authToken"
            :images="point.docs_images"
          />
        </article>
      </section>
    </section>
  </section>
</template>

<style scoped>
.details-page {
  display: grid;
  gap: 0.9rem;
  width: 100%;
  max-width: 1100px;
  margin: 0 auto;
  min-width: 0;
}
.card {
  border: 1px solid #243043;
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.85), rgba(2, 6, 23, 0.95));
  box-shadow: 0 10px 28px rgba(2, 6, 23, 0.28);
  padding: 1rem;
}
.details-card {
  display: grid;
  gap: 0.8rem;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}
.top-actions {
  align-items: center;
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
  background: #ef4444;
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.2);
}
.reassign-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}
.point-view-grid {
  display: grid;
  gap: 0.3rem;
}
.point-view-grid p {
  margin: 0;
}
.summary-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.45rem 1rem;
  padding: 0.15rem 0 0.25rem;
}
.head h2 {
  margin: 0;
  font-size: 1.15rem;
}
.points-wrap h3,
.edit-card h3 {
  margin: 0;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-label);
}
.meta-line {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.84rem;
  line-height: 1.4;
}
.muted-value {
  color: var(--text-muted) !important;
  font-weight: 500;
}
.edit-card {
  border: 1px solid #243043;
  border-radius: 12px;
  padding: 0.75rem;
  background: rgba(15, 23, 42, 0.7);
}
.edit-grid,
.point-edit-grid {
  display: grid;
  gap: 0.55rem;
}
.points-wrap {
  display: grid;
  gap: 0.55rem;
}
.points-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}
.point-card {
  border: 1px solid #243043;
  border-radius: 12px;
  background: rgba(2, 6, 23, 0.5);
  padding: 0.7rem;
  display: grid;
  gap: 0.45rem;
}
.point-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}
.point-top strong {
  color: var(--text-heading);
  font-size: 0.98rem;
  line-height: 1.35;
}
.point-edit-grid .full {
  grid-column: 1 / -1;
}
.point-full-edit {
  display: grid;
  gap: 0.7rem;
  padding: 0.7rem;
  border: 1px solid #334155;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.55);
}
.point-full-edit h4 {
  margin: 0.2rem 0 0;
  font-size: 0.92rem;
}
.stage-edit-grid {
  display: grid;
  gap: 0.5rem;
}
.stage-edit-title {
  margin: 0.35rem 0 0;
  font-weight: 700;
  color: #cbd5e1;
  grid-column: 1 / -1;
}
.edit-hint {
  display: block;
  margin-top: 0.15rem;
  color: #fbbf24;
  font-size: 0.75rem;
}
.stage-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  max-width: 100%;
}
.stage-table {
  min-width: 520px;
}
.stage-table th,
.stage-table td {
  padding: 0.5rem 0.45rem;
  border-bottom: 1px solid #243043;
}
.stage-table th {
  font-size: 0.72rem;
  font-weight: 650;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-label);
}
.stage-table td {
  color: var(--text-body);
  font-size: 0.9rem;
}
.status-chip {
  border: 1px solid #334155;
  border-radius: 999px;
  padding: 0.1rem 0.5rem;
  font-size: 0.8rem;
  color: #c7d2fe;
}
.maps-link {
  color: #93c5fd;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.muted {
  margin: 0;
  color: #94a3b8;
  font-size: 0.86rem;
}
.error {
  margin: 0;
  color: #fca5a5;
}
.ok {
  color: #86efac;
  font-weight: 650;
}
label {
  display: grid;
  gap: 0.26rem;
  color: var(--text-label);
  font-size: 0.8rem;
}
input,
select,
textarea {
  width: 100%;
  border-radius: 10px;
  border: 1px solid #334155;
  background: #0b1220;
  color: #fff;
  padding: 0.5rem 0.62rem;
}
.upper {
  text-transform: uppercase;
}
button {
  border: none;
  border-radius: 10px;
  padding: 0.48rem 0.72rem;
  color: #fff;
}
.secondary {
  background: #3b82f6;
}
.danger {
  background: #ef4444;
}
.danger.soft {
  background: #7f1d1d;
}
.ghost {
  background: transparent;
  border: 1px solid #334155;
  color: #cbd5e1;
}
@media (min-width: 900px) {
  .edit-grid,
  .point-edit-grid,
  .stage-edit-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
  .stage-edit-title {
    grid-column: 1 / -1;
  }
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
