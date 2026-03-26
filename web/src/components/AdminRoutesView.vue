<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

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
  point_time: string;
};

const props = defineProps<{
  routes: AdminRoute[];
  drivers: DriverOption[];
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
}>();

const statusTabs: Array<{ label: string; value: RouteWorkflowStatus }> = [
  { label: "Не приняты", value: "new" },
  { label: "В процессе", value: "process" },
  { label: "Завершены", value: "success" },
  { label: "Отменён", value: "cancelled" }
];

const showCreate = ref(false);
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

const STATUS_LABELS: Record<RouteWorkflowStatus, string> = {
  new: "Не принят",
  process: "В процессе",
  success: "Завершён",
  cancelled: "Отменён"
};

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

onMounted(() => {
  doSearch();
});
</script>

<template>
  <section class="admin-routes-page">
    <button v-if="!showCreate" class="ghost create-toggle" :disabled="loading || !drivers.length" @click="openCreate">+ Создать рейс</button>

    <section v-if="!showCreate" class="card">
      <h2>Выберите статус</h2>
      <div class="tabs">
        <button
          v-for="tab in statusTabs"
          :key="tab.value"
          :class="['tab-btn', { active: tab.value === filters.status }]"
          type="button"
          @click="setStatusTab(tab.value)"
        >
          {{ tab.label }}
        </button>
      </div>
    </section>

    <section v-if="!showCreate" class="card filters-card">
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
          <button class="secondary" type="button" :disabled="loading" @click="doSearch">Применить</button>
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
              <td>{{ STATUS_LABELS[route.status] ?? route.status }}</td>
            </tr>
            <tr v-if="!routes.length">
              <td colspan="4" class="empty">Рейсы не найдены</td>
            </tr>
          </tbody>
        </table>
      </div>
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
          <button class="secondary" type="button" @click="addCreatePoint">Добавить точку</button>
      </div>
      <article v-for="(point, idx) in createForm.points" :key="`new-${idx}`" class="point-card">
        <div class="point-top">
          <strong>Точка {{ idx + 1 }}</strong>
          <button class="danger soft" type="button" @click="removeCreatePoint(idx)">Удалить</button>
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
            <input v-model="point.date_point" type="date" />
          </label>
          <label>
            Время
            <input v-model="point.point_time" type="time" step="60" />
          </label>
        </div>
      </article>
      <div class="actions">
        <button class="primary" type="button" @click="submitCreate">Сохранить</button>
        <button class="ghost" type="button" @click="showCreate = false">Отмена</button>
      </div>
    </section>
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
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}
.create-grid {
  display: grid;
  gap: 0.55rem;
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
@media (min-width: 900px) {
  .filters-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
  .create-grid,
  .point-edit-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
</style>

