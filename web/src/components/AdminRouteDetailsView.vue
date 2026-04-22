<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";

import PointDocThumbs from "./PointDocThumbs.vue";
import type { AdminRoute, AdminRoutePointPayload, DriverOption, RouteWorkflowStatus } from "../types";

type PointForm = {
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
}>();

const showReassign = ref(false);
const showEdit = ref(false);
const reassignDriverId = ref(0);

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

function makeEmptyPoint(): PointForm {
  return {
    type_point: "loading",
    place_point: "",
    date_point: "",
    point_time: ""
  };
}

function toPointPayload(points: PointForm[]): AdminRoutePointPayload[] {
  return points.map((point, index) => ({
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
      type_point: point.type_point || "loading",
      place_point: point.place_point || "",
      date_point: point.date_point || "",
      point_time: point.point_time || ""
    }));
    reassignDriverId.value = route.driver?.id ?? 0;
    showReassign.value = false;
    showEdit.value = false;
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
        <button class="ghost" @click="emit('back')">← К списку</button>
      </div>

      <div class="summary-grid">
        <p><strong>N рейса:</strong> {{ route.id }}</p>
        <p><strong>Водитель:</strong> {{ route.driver?.full_name || route.driver?.login || "—" }}</p>
        <p><strong>ТС:</strong> {{ route.number_auto || "—" }}</p>
        <p><strong>Прицеп:</strong> {{ route.trailer_number || "—" }}</p>
        <p><strong>Статус:</strong> {{ routeStatusWithCurrentPoint(route) }}</p>
        <p><strong>Температура:</strong> {{ route.temperature || "—" }}</p>
        <p><strong>Контакты диспетчера:</strong> {{ route.dispatcher_contacts || "—" }}</p>
        <p><strong>N регистрации:</strong> {{ route.registration_number || "—" }}</p>
      </div>
      <div class="actions">
        <button class="secondary" type="button" @click="emit('openChat', route.id)">Открыть чат рейса</button>
      </div>

      <section v-if="showEdit" class="edit-card">
        <h3>Редактирование рейса</h3>
        <div class="edit-grid">
          <label>
            Номер авто
            <input v-model="editForm.number_auto" />
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
            <input v-model="editForm.trailer_number" />
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
            <strong>{{ pointTypeLabel(point.type_point) }} · {{ point.place_point || "Без адреса" }}</strong>
            <span class="status-chip">{{ pointStatusLabel(point.status) }}</span>
          </div>
          <p class="muted">{{ point.date_point || "—" }} · {{ point.point_time || "—" }}</p>
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
                <td>{{ point.departure_time || point.time_accepted || "—" }}</td>
                <td>{{ point.departure_odometer || "—" }}</td>
                <td>{{ point.departure_coordinates?.lat ?? "—" }}, {{ point.departure_coordinates?.lng ?? "—" }}</td>
              </tr>
              <tr>
                <td>{{ normalizePointStageLabel("registration") }}</td>
                <td>{{ point.registration_time || point.time_registration || "—" }}</td>
                <td>{{ point.registration_odometer || "—" }}</td>
                <td>{{ point.registration_coordinates?.lat ?? "—" }}, {{ point.registration_coordinates?.lng ?? "—" }}</td>
              </tr>
              <tr>
                <td>{{ normalizePointStageLabel("load") }}</td>
                <td>{{ point.gate_time || point.time_put_on_gate || "—" }}</td>
                <td>{{ point.gate_odometer || "—" }}</td>
                <td>{{ point.gate_coordinates?.lat ?? "—" }}, {{ point.gate_coordinates?.lng ?? "—" }}</td>
              </tr>
              <tr>
                <td>{{ normalizePointStageLabel("docs") }}</td>
                <td>{{ point.docs_time || point.time_docs || "—" }}</td>
                <td>{{ point.docs_odometer || "—" }}</td>
                <td>{{ point.docs_coordinates?.lat ?? "—" }}, {{ point.docs_coordinates?.lng ?? "—" }}</td>
              </tr>
            </tbody>
          </table>
          </div>
          <PointDocThumbs
            v-if="authToken && point.docs_images?.length"
            :token="authToken"
            :images="point.docs_images"
          />
        </article>
      </section>

      <section class="actions route-actions-bottom">
        <button class="secondary" v-if="!showEdit" :disabled="loading" @click="openEdit">Редактировать</button>
        <button
          class="secondary"
          v-if="!showReassign"
          :disabled="loading"
          @click="openReassign"
        >
          Переназначить
        </button>
        <div v-if="showReassign" class="reassign-wrap">
          <select v-model.number="reassignDriverId">
            <option :value="0">Выберите водителя</option>
            <option v-for="driver in drivers" :key="driver.id" :value="driver.id">
              {{ driver.full_name || driver.login }}
            </option>
          </select>
          <button
            class="secondary"
            :disabled="loading || !canAssign"
            @click="submitReassign"
          >
            Сохранить
          </button>
          <button class="ghost" @click="closeReassign">Отмена</button>
        </div>
        <button class="danger" :disabled="loading || !canCancel(route.status)" @click="emit('cancelRoute', route.id)">
          Отменить
        </button>
        <button class="danger soft" :disabled="loading" @click="removeRoute">Удалить рейс</button>
      </section>
    </section>
  </section>
</template>

<style scoped>
.details-page {
  display: grid;
  gap: 0.9rem;
  width: 100%;
  max-width: 100%;
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
.route-actions-bottom {
  margin-top: 0.4rem;
  padding-top: 0.6rem;
  border-top: 1px solid #243043;
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
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.45rem 0.8rem;
}
.summary-grid p {
  margin: 0;
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
.point-edit-grid .full {
  grid-column: 1 / -1;
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
  padding: 0.45rem;
  border-bottom: 1px solid #243043;
}
.status-chip {
  border: 1px solid #334155;
  border-radius: 999px;
  padding: 0.1rem 0.5rem;
  font-size: 0.8rem;
  color: #c7d2fe;
}
.muted {
  margin: 0;
  color: #94a3b8;
  font-size: 0.86rem;
}
label {
  display: grid;
  gap: 0.26rem;
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
  .point-edit-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 700px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
