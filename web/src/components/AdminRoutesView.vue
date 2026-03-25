<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";

import type { AdminRoute, AdminRoutePointPayload, DriverOption, RouteWorkflowStatus } from "../types";

type RouteSearchFilters = {
  status?: string;
  route_id?: string;
  number_auto?: string;
  driver_query?: string;
};

type PointForm = {
  type_point: string;
  place_point: string;
  date_point: string;
  point_name: string;
  point_contacts: string;
  point_time: string;
  point_note: string;
};

const props = defineProps<{
  routes: AdminRoute[];
  drivers: DriverOption[];
  selectedRoute: AdminRoute | null;
  loading: boolean;
  error: string;
}>();

const emit = defineEmits<{
  refresh: [filters?: RouteSearchFilters];
  create: [
    payload: {
      route_id: string;
      driver_user_id: number;
      number_auto?: string;
      temperature?: string;
      dispatcher_contacts?: string;
      registration_number?: string;
      trailer_number?: string;
      points: AdminRoutePointPayload[];
    }
  ];
  selectRoute: [routeId: string];
  assignDriver: [routeId: string, driverUserId: number];
  cancelRoute: [routeId: string];
  completeRoute: [routeId: string];
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
}>();

const statusTabs: Array<{ label: string; value: string }> = [
  { label: "Не приняты", value: "new" },
  { label: "В процессе", value: "process" },
  { label: "Завершены", value: "success" },
  { label: "Отменён", value: "cancelled" }
];

const showCreate = ref(false);
const assignSelections = reactive<Record<string, number>>({});

const filters = reactive({
  route_id: "",
  number_auto: "",
  driver_query: "",
  status: "process"
});

const selectedTabLabel = computed(() => {
  const tab = statusTabs.find((item) => item.value === filters.status);
  return tab?.label ?? "Все";
});

const filteredTitle = computed(() => `Рейсы (${selectedTabLabel.value}) — ${props.routes.length}`);

const createForm = reactive({
  route_id: "",
  driver_user_id: 0,
  number_auto: "",
  temperature: "",
  dispatcher_contacts: "",
  registration_number: "",
  trailer_number: "",
  points: [] as PointForm[]
});

const editForm = reactive({
  number_auto: "",
  temperature: "",
  dispatcher_contacts: "",
  registration_number: "",
  trailer_number: "",
  points: [] as PointForm[]
});

function makeEmptyPoint(): PointForm {
  return {
    type_point: "loading",
    place_point: "",
    date_point: "",
    point_name: "",
    point_contacts: "",
    point_time: "",
    point_note: ""
  };
}

function toPointPayload(points: PointForm[]): AdminRoutePointPayload[] {
  return points.map((point, index) => ({
    type_point: point.type_point || "loading",
    place_point: point.place_point.trim(),
    date_point: point.date_point.trim(),
    point_name: point.point_name.trim(),
    point_contacts: point.point_contacts.trim(),
    point_time: point.point_time.trim(),
    point_note: point.point_note.trim(),
    order_index: index
  }));
}

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
  const current = (route.points || []).find((point) => point.status !== "success");
  if (!current) {
    return base;
  }
  return `${base} · Точка #${current.id}`;
}

function pointTypeLabel(value: string): string {
  return value === "unloading" ? "Выгрузка" : "Загрузка";
}

function normalizePointStageLabel(stage: string): string {
  const labels: Record<string, string> = {
    accepted: "Принят",
    registration: "Регистрация",
    load: "На воротах",
    docs: "Документы",
    departure: "Выехал"
  };
  return labels[stage] ?? stage;
}

function canCancel(status: RouteWorkflowStatus): boolean {
  return status === "new" || status === "process";
}

function canComplete(route: AdminRoute): boolean {
  if (route.status !== "process") {
    return false;
  }
  const points = route.points ?? [];
  return points.length > 0 && points.every((point) => point.status === "success");
}

function selectedAssignDriver(routeId: string): number {
  return assignSelections[routeId] ?? 0;
}

function setStatusTab(status: string): void {
  filters.status = status;
  doSearch();
}

function doSearch(): void {
  const payload: RouteSearchFilters = {};
  if (filters.status.trim()) {
    payload.status = filters.status.trim();
  }
  if (filters.route_id.trim()) {
    payload.route_id = filters.route_id.trim();
  }
  if (filters.number_auto.trim()) {
    payload.number_auto = filters.number_auto.trim();
  }
  if (filters.driver_query.trim()) {
    payload.driver_query = filters.driver_query.trim();
  }
  emit("refresh", payload);
}

function openCreate(): void {
  showCreate.value = true;
  createForm.route_id = "";
  createForm.driver_user_id = props.drivers[0]?.id ?? 0;
  createForm.number_auto = "";
  createForm.temperature = "";
  createForm.dispatcher_contacts = "";
  createForm.registration_number = "";
  createForm.trailer_number = "";
  createForm.points = [];
}

function addCreatePoint(): void {
  createForm.points.push(makeEmptyPoint());
}

function removeCreatePoint(index: number): void {
  createForm.points.splice(index, 1);
}

function submitCreate(): void {
  if (!createForm.route_id.trim() || !createForm.driver_user_id) {
    return;
  }
  emit("create", {
    route_id: createForm.route_id.trim(),
    driver_user_id: createForm.driver_user_id,
    number_auto: createForm.number_auto.trim(),
    temperature: createForm.temperature.trim(),
    dispatcher_contacts: createForm.dispatcher_contacts.trim(),
    registration_number: createForm.registration_number.trim(),
    trailer_number: createForm.trailer_number.trim(),
    points: toPointPayload(createForm.points).filter((point) => point.place_point && point.date_point)
  });
  showCreate.value = false;
}

watch(
  () => props.selectedRoute,
  (route) => {
    if (!route) {
      editForm.number_auto = "";
      editForm.temperature = "";
      editForm.dispatcher_contacts = "";
      editForm.registration_number = "";
      editForm.trailer_number = "";
      editForm.points = [];
      return;
    }
    editForm.number_auto = route.number_auto || "";
    editForm.temperature = route.temperature || "";
    editForm.dispatcher_contacts = route.dispatcher_contacts || "";
    editForm.registration_number = route.registration_number || "";
    editForm.trailer_number = route.trailer_number || "";
    editForm.points = (route.points || []).map((point) => ({
      type_point: point.type_point || "loading",
      place_point: point.place_point || "",
      date_point: point.date_point || "",
      point_name: point.point_name || "",
      point_contacts: point.point_contacts || "",
      point_time: point.point_time || "",
      point_note: point.point_note || ""
    }));
  },
  { immediate: true }
);

function addEditPoint(): void {
  editForm.points.push(makeEmptyPoint());
}

function removeEditPoint(index: number): void {
  editForm.points.splice(index, 1);
}

function submitEdit(): void {
  if (!props.selectedRoute) {
    return;
  }
  emit("updateRoute", props.selectedRoute.id, {
    number_auto: editForm.number_auto.trim(),
    temperature: editForm.temperature.trim(),
    dispatcher_contacts: editForm.dispatcher_contacts.trim(),
    registration_number: editForm.registration_number.trim(),
    trailer_number: editForm.trailer_number.trim(),
    points: toPointPayload(editForm.points).filter((point) => point.place_point && point.date_point)
  });
}

onMounted(() => {
  doSearch();
});
</script>

<template>
  <section class="admin-routes-page">
    <section class="card">
      <h2>Выберите статус</h2>
      <div class="tabs">
        <button
          v-for="tab in statusTabs"
          :key="tab.value"
          :class="['tab-btn', { active: tab.value === filters.status }]"
          @click="setStatusTab(tab.value)"
        >
          {{ tab.label }}
        </button>
      </div>
    </section>

    <section class="card filters-card">
      <h2>{{ filteredTitle }}</h2>
      <div class="filters-grid">
        <label>
          Водитель (часть ФИО)
          <input v-model="filters.driver_query" placeholder="Иванов" />
        </label>
        <label>
          № рейса
          <input v-model="filters.route_id" placeholder="R-2026-01" />
        </label>
        <label>
          ТС
          <input v-model="filters.number_auto" placeholder="А123ВС777" />
        </label>
        <div class="apply-wrap">
          <button class="secondary" :disabled="loading" @click="doSearch">Применить</button>
        </div>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>№ рейса</th>
              <th>Водитель</th>
              <th>ТС</th>
              <th>Статус</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="route in routes" :key="route.id" @click="emit('selectRoute', route.id)">
              <td>{{ route.id }}</td>
              <td>{{ route.driver?.full_name || route.driver?.login || "—" }}</td>
              <td>{{ route.number_auto || "—" }}</td>
              <td>{{ statusLabel(route.status) }}</td>
            </tr>
            <tr v-if="!routes.length">
              <td colspan="4" class="empty">Рейсы не найдены</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="selectedRoute" class="card details-card">
      <div class="head">
        <h2>Рейс {{ selectedRoute.id }}</h2>
        <div class="actions">
          <select v-model.number="assignSelections[selectedRoute.id]">
            <option :value="0">Назначить водителя</option>
            <option v-for="driver in drivers" :key="driver.id" :value="driver.id">
              {{ driver.full_name || driver.login }}
            </option>
          </select>
          <button
            class="secondary"
            :disabled="loading || !selectedAssignDriver(selectedRoute.id)"
            @click="emit('assignDriver', selectedRoute.id, selectedAssignDriver(selectedRoute.id))"
          >
            Назначить
          </button>
          <button class="danger" :disabled="loading || !canCancel(selectedRoute.status)" @click="emit('cancelRoute', selectedRoute.id)">
            Отменить
          </button>
          <button class="primary" :disabled="loading || !canComplete(selectedRoute)" @click="emit('completeRoute', selectedRoute.id)">
            Завершить
          </button>
        </div>
      </div>

      <div class="summary-grid">
        <p><strong>N рейса:</strong> {{ selectedRoute.id }}</p>
        <p><strong>Водитель:</strong> {{ selectedRoute.driver?.full_name || selectedRoute.driver?.login || "—" }}</p>
        <p><strong>ТС:</strong> {{ selectedRoute.number_auto || "—" }}</p>
        <p><strong>Прицеп:</strong> {{ selectedRoute.trailer_number || "—" }}</p>
        <p><strong>Статус:</strong> {{ routeStatusWithCurrentPoint(selectedRoute) }}</p>
        <p><strong>Температура:</strong> {{ selectedRoute.temperature || "—" }}</p>
        <p><strong>Контакты диспетчера:</strong> {{ selectedRoute.dispatcher_contacts || "—" }}</p>
        <p><strong>N регистрации:</strong> {{ selectedRoute.registration_number || "—" }}</p>
      </div>

      <section class="edit-card">
        <h3>Редактирование ключевых полей</h3>
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
      </section>

      <section class="points-wrap">
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
          <p class="muted">{{ point.point_name || point.place_point || "—" }}</p>
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
              <input v-model="point.date_point" />
            </label>
            <label>
              Время
              <input v-model="point.point_time" />
            </label>
            <label>
              Название
              <input v-model="point.point_name" />
            </label>
            <label>
              Адрес
              <input v-model="point.place_point" />
            </label>
            <label>
              Контакты
              <input v-model="point.point_contacts" />
            </label>
            <label class="full">
              Примечание
              <textarea v-model="point.point_note" rows="2" />
            </label>
          </div>
        </article>
        <button class="primary" :disabled="loading" @click="submitEdit">Сохранить изменения</button>
      </section>

      <section class="points-wrap">
        <h3>Этапы по точкам</h3>
        <article v-for="point in selectedRoute.points || []" :key="point.id" class="point-card">
          <div class="point-top">
            <strong>{{ pointTypeLabel(point.type_point) }} · {{ point.point_name || point.place_point || "Без названия" }}</strong>
            <span class="status-chip">{{ point.status }}</span>
          </div>
          <p class="muted">{{ point.date_point || "—" }} · {{ point.point_time || "—" }}</p>
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
                <td>{{ point.time_accepted || "—" }}</td>
                <td>{{ point.odometer || "—" }}</td>
                <td>{{ point.coordinates?.lat ?? "—" }}, {{ point.coordinates?.lng ?? "—" }}</td>
              </tr>
              <tr>
                <td>{{ normalizePointStageLabel("registration") }}</td>
                <td>{{ point.time_registration || "—" }}</td>
                <td>—</td>
                <td>—</td>
              </tr>
              <tr>
                <td>{{ normalizePointStageLabel("load") }}</td>
                <td>{{ point.time_put_on_gate || "—" }}</td>
                <td>—</td>
                <td>—</td>
              </tr>
              <tr>
                <td>{{ normalizePointStageLabel("docs") }}</td>
                <td>{{ point.time_docs || "—" }}</td>
                <td>—</td>
                <td>—</td>
              </tr>
              <tr>
                <td>{{ normalizePointStageLabel("departure") }}</td>
                <td>{{ point.time_departure || "—" }}</td>
                <td>—</td>
                <td>—</td>
              </tr>
            </tbody>
          </table>
        </article>
      </section>
    </section>

    <section v-if="showCreate" class="card create-card">
      <h2>Создать рейс</h2>
      <div class="create-grid">
        <label>
          ID рейса
          <input v-model="createForm.route_id" placeholder="R-2026-0001" />
        </label>
        <label>
          Водитель
          <select v-model.number="createForm.driver_user_id">
            <option v-for="driver in drivers" :key="driver.id" :value="driver.id">
              {{ driver.full_name || driver.login }}
            </option>
          </select>
        </label>
        <label>
          Номер авто
          <input v-model="createForm.number_auto" />
        </label>
        <label>
          Температура
          <input v-model="createForm.temperature" />
        </label>
        <label>
          Контакты диспетчера
          <input v-model="createForm.dispatcher_contacts" />
        </label>
        <label>
          Номер регистрации
          <input v-model="createForm.registration_number" />
        </label>
        <label>
          Номер прицепа
          <input v-model="createForm.trailer_number" />
        </label>
      </div>
      <div class="actions">
        <button class="secondary" @click="addCreatePoint">Добавить точку</button>
      </div>
      <article v-for="(point, idx) in createForm.points" :key="`new-${idx}`" class="point-card">
        <div class="point-top">
          <strong>Точка {{ idx + 1 }}</strong>
          <button class="danger soft" @click="removeCreatePoint(idx)">Удалить</button>
        </div>
        <div class="point-edit-grid">
          <label>
            Тип
            <select v-model="point.type_point">
              <option value="loading">Загрузка</option>
              <option value="unloading">Выгрузка</option>
            </select>
          </label>
          <label>
            Адрес
            <input v-model="point.place_point" />
          </label>
          <label>
            Дата
            <input v-model="point.date_point" />
          </label>
          <label>
            Название
            <input v-model="point.point_name" />
          </label>
          <label>
            Контакты
            <input v-model="point.point_contacts" />
          </label>
          <label>
            Время
            <input v-model="point.point_time" />
          </label>
          <label class="full">
            Примечание
            <textarea v-model="point.point_note" rows="2" />
          </label>
        </div>
      </article>
      <div class="actions">
        <button class="primary" @click="submitCreate">Сохранить</button>
        <button class="ghost" @click="showCreate = false">Отмена</button>
      </div>
    </section>
    <button v-else class="ghost create-toggle" :disabled="loading || !drivers.length" @click="openCreate">+ Новый рейс</button>
  </section>
</template>

<style scoped>
.admin-routes-page {
  display: grid;
  gap: 0.9rem;
}
.card {
  border: 1px solid #243043;
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.85), rgba(2, 6, 23, 0.95));
  box-shadow: 0 10px 28px rgba(2, 6, 23, 0.28);
  padding: 1rem;
}
.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.tab-btn {
  width: auto;
  border: 1px solid #334155;
  border-radius: 10px;
  background: #111827;
  color: #dbeafe;
  padding: 0.45rem 0.7rem;
}
.tab-btn.active {
  background: #4f46e5;
  border-color: #6366f1;
}
.filters-grid {
  display: grid;
  gap: 0.6rem;
}
.apply-wrap {
  display: flex;
  align-items: end;
}
.table-wrap {
  margin-top: 0.75rem;
  overflow-x: auto;
  border: 1px solid #243043;
  border-radius: 12px;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th,
td {
  text-align: left;
  padding: 0.65rem;
  border-bottom: 1px solid #243043;
}
tbody tr {
  cursor: pointer;
}
tbody tr:hover {
  background: rgba(79, 70, 229, 0.12);
}
.empty {
  text-align: center;
  color: #94a3b8;
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
.create-grid {
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
.point-edit-grid {
  display: grid;
  gap: 0.5rem;
}
.point-edit-grid .full {
  grid-column: 1 / -1;
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
.error {
  margin: 0.45rem 0 0;
  color: #fca5a5;
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
.primary {
  background: #10b981;
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
.create-toggle {
  justify-self: start;
}
@media (min-width: 900px) {
  .filters-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
  .edit-grid,
  .create-grid,
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

