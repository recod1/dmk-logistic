<script setup lang="ts">
import { reactive, ref, watch } from "vue";

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

const showCreate = ref(false);
const assignSelections = reactive<Record<string, number>>({});

const filters = reactive({
  route_id: "",
  number_auto: "",
  driver_query: "",
  status: ""
});

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

function selectedAssignDriver(routeId: string): number {
  return assignSelections[routeId] ?? 0;
}

function statusLabel(status: RouteWorkflowStatus): string {
  const labels: Record<RouteWorkflowStatus, string> = {
    new: "Новый",
    process: "В процессе",
    success: "Завершён",
    cancelled: "Отменён"
  };
  return labels[status] ?? status;
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

function clearSearch(): void {
  filters.status = "";
  filters.route_id = "";
  filters.number_auto = "";
  filters.driver_query = "";
  emit("refresh", {});
}
</script>

<template>
  <section class="routes-wrap">
    <div class="head-row">
      <h1>Рейсы</h1>
      <div class="actions">
        <button :disabled="loading" @click="emit('refresh')">Обновить</button>
        <button :disabled="loading || !drivers.length" @click="openCreate">Создать рейс</button>
      </div>
    </div>

    <section class="card search-card">
      <h2>Поиск рейсов</h2>
      <label>
        ID рейса
        <input v-model="filters.route_id" placeholder="Например, R-2026-001" />
      </label>
      <label>
        Номер ТС
        <input v-model="filters.number_auto" placeholder="А123ВС777" />
      </label>
      <label>
        Водитель (логин/ФИО)
        <input v-model="filters.driver_query" placeholder="Иванов" />
      </label>
      <label>
        Статус
        <select v-model="filters.status">
          <option value="">Все</option>
          <option value="new">Новый</option>
          <option value="process">В процессе</option>
          <option value="success">Завершён</option>
          <option value="cancelled">Отменён</option>
        </select>
      </label>
      <div class="actions">
        <button :disabled="loading" @click="doSearch">Найти</button>
        <button :disabled="loading" @click="clearSearch">Сбросить</button>
      </div>
    </section>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="routes-list">
      <article v-for="route in routes" :key="route.id" class="card route-item">
        <div class="row">
          <strong>#{{ route.id }}</strong>
          <span class="chip">{{ statusLabel(route.status) }}</span>
        </div>
        <p><strong>Водитель:</strong> {{ route.driver?.full_name || route.driver?.login || "—" }}</p>
        <p><strong>ТС:</strong> {{ route.number_auto || "—" }}</p>
        <p><strong>Точек:</strong> {{ route.points_count }}</p>
        <div class="actions wrap">
          <button :disabled="loading" @click="emit('selectRoute', route.id)">Открыть</button>
          <select v-model.number="assignSelections[route.id]">
            <option :value="0">Назначить водителя</option>
            <option v-for="driver in drivers" :key="driver.id" :value="driver.id">
              {{ driver.full_name || driver.login }}
            </option>
          </select>
          <button
            :disabled="loading || !selectedAssignDriver(route.id)"
            @click="emit('assignDriver', route.id, selectedAssignDriver(route.id))"
          >
            Назначить
          </button>
          <button :disabled="loading || !canCancel(route.status)" @click="emit('cancelRoute', route.id)">Отменить</button>
          <button :disabled="loading || !canComplete(route)" @click="emit('completeRoute', route.id)">Завершить</button>
        </div>
      </article>
      <p v-if="!routes.length" class="empty">Рейсы не найдены</p>
    </div>

    <section v-if="showCreate" class="card form-card">
      <h2>Создать рейс</h2>
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
        Номер для регистрации
        <input v-model="createForm.registration_number" />
      </label>
      <label>
        Номер прицепа
        <input v-model="createForm.trailer_number" />
      </label>

      <h3>Точки рейса</h3>
      <div class="actions">
        <button @click="addCreatePoint">Добавить точку</button>
      </div>
      <article v-for="(point, idx) in createForm.points" :key="`new-${idx}`" class="point-card">
        <div class="row">
          <strong>Точка {{ idx + 1 }}</strong>
          <button @click="removeCreatePoint(idx)">Удалить</button>
        </div>
        <label>
          Тип точки
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
        <label>
          Примечание
          <textarea v-model="point.point_note" rows="2" />
        </label>
      </article>

      <div class="actions">
        <button @click="submitCreate">Сохранить</button>
        <button @click="showCreate = false">Отмена</button>
      </div>
    </section>

    <section v-if="selectedRoute" class="card form-card">
      <h2>Редактировать рейс #{{ selectedRoute.id }}</h2>
      <p><strong>Статус:</strong> {{ statusLabel(selectedRoute.status) }}</p>
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
        Номер для регистрации
        <input v-model="editForm.registration_number" />
      </label>
      <label>
        Номер прицепа
        <input v-model="editForm.trailer_number" />
      </label>

      <h3>Точки</h3>
      <div class="actions">
        <button @click="addEditPoint">Добавить точку</button>
      </div>
      <article v-for="(point, idx) in editForm.points" :key="`edit-${idx}`" class="point-card">
        <div class="row">
          <strong>Точка {{ idx + 1 }}</strong>
          <button @click="removeEditPoint(idx)">Удалить</button>
        </div>
        <label>
          Тип точки
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
        <label>
          Примечание
          <textarea v-model="point.point_note" rows="2" />
        </label>
      </article>

      <div class="actions">
        <button :disabled="loading" @click="submitEdit">Сохранить изменения</button>
      </div>
    </section>
  </section>
</template>

<style scoped>
.routes-wrap {
  display: grid;
  gap: 0.8rem;
}
.head-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.6rem;
}
.actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.wrap {
  flex-wrap: wrap;
}
.search-card,
.form-card {
  display: grid;
  gap: 0.55rem;
}
.routes-list {
  display: grid;
  gap: 0.6rem;
}
.route-item {
  display: grid;
  gap: 0.35rem;
}
.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.chip {
  border-radius: 999px;
  background: #1f2937;
  padding: 0.1rem 0.6rem;
  color: #d1d5db;
  font-size: 0.86rem;
}
.point-card {
  border: 1px solid #374151;
  border-radius: 10px;
  padding: 0.65rem;
  background: #0b1220;
  display: grid;
  gap: 0.45rem;
}
.empty {
  color: #9ca3af;
  margin: 0;
}
.error {
  color: #fca5a5;
}
label {
  display: grid;
  gap: 0.3rem;
}
input,
select,
textarea,
button {
  width: 100%;
  border-radius: 8px;
  border: 1px solid #374151;
  background: #0b1220;
  color: #fff;
  padding: 0.45rem 0.6rem;
}
button {
  background: #2563eb;
  border: none;
}
.card {
  border: 1px solid #374151;
  border-radius: 12px;
  background: #111827;
  padding: 0.85rem;
}
@media (min-width: 760px) {
  .search-card {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 760px) {
  .actions > button,
  .actions > select {
    flex: 1 1 calc(50% - 0.3rem);
    min-width: 0;
  }
}
</style>

