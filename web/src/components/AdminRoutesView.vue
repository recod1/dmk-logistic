<script setup lang="ts">
import { computed, reactive, ref } from "vue";

import type { AdminRoute, DriverOption } from "../types";

const props = defineProps<{
  routes: AdminRoute[];
  drivers: DriverOption[];
  selectedRoute: AdminRoute | null;
  loading: boolean;
  error: string;
}>();

const emit = defineEmits<{
  refresh: [];
  create: [
    payload: {
      route_id: string;
      driver_user_id: number;
      number_auto?: string;
      temperature?: string;
      dispatcher_contacts?: string;
      registration_number?: string;
      trailer_number?: string;
      points: Array<{ type_point: string; date_point: string; place_point: string; order_index: number }>;
    }
  ];
  selectRoute: [routeId: string];
  assignDriver: [routeId: string, driverUserId: number];
}>();

const showCreate = ref(false);
const createForm = reactive({
  route_id: "",
  driver_user_id: 0,
  number_auto: "",
  temperature: "",
  dispatcher_contacts: "",
  registration_number: "",
  trailer_number: "",
  points_text: ""
});

const assignSelections = reactive<Record<string, number>>({});

const driversById = computed(() => new Map(props.drivers.map((driver) => [driver.id, driver])));

function openCreate(): void {
  showCreate.value = true;
  createForm.route_id = "";
  createForm.driver_user_id = props.drivers[0]?.id ?? 0;
  createForm.number_auto = "";
  createForm.temperature = "";
  createForm.dispatcher_contacts = "";
  createForm.registration_number = "";
  createForm.trailer_number = "";
  createForm.points_text = "";
}

function parsePoints(text: string): Array<{ type_point: string; date_point: string; place_point: string; order_index: number }> {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, idx) => {
      const [type, date, ...rest] = line.split("|");
      return {
        type_point: (type || "loading").trim().toLowerCase(),
        date_point: (date || "").trim(),
        place_point: rest.join("|").trim(),
        order_index: idx
      };
    })
    .filter((point) => point.place_point && point.date_point);
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
    points: parsePoints(createForm.points_text)
  });
  showCreate.value = false;
}

function selectedAssignDriver(routeId: string): number {
  return assignSelections[routeId] ?? 0;
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

    <p v-if="error" class="error">{{ error }}</p>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Статус</th>
            <th>Водитель</th>
            <th>ТС</th>
            <th>Точки</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="route in routes" :key="route.id">
            <td>{{ route.id }}</td>
            <td>{{ route.status }}</td>
            <td>{{ route.driver?.full_name || route.driver?.login || "—" }}</td>
            <td>{{ route.number_auto || "—" }}</td>
            <td>{{ route.points_count }}</td>
            <td class="row-actions">
              <button :disabled="loading" @click="emit('selectRoute', route.id)">Открыть</button>
              <select v-model.number="assignSelections[route.id]">
                <option :value="0">Назначить...</option>
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
            </td>
          </tr>
          <tr v-if="!routes.length">
            <td colspan="6" class="empty">Рейсы не найдены</td>
          </tr>
        </tbody>
      </table>
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
      <label>
        Точки (по одной на строку: type|date|place)
        <textarea v-model="createForm.points_text" rows="5" />
      </label>
      <div class="actions">
        <button @click="submitCreate">Сохранить</button>
        <button @click="showCreate = false">Отмена</button>
      </div>
    </section>

    <section v-if="selectedRoute" class="card detail-card">
      <h2>Рейс #{{ selectedRoute.id }}</h2>
      <p><strong>Статус:</strong> {{ selectedRoute.status }}</p>
      <p><strong>Водитель:</strong> {{ selectedRoute.driver?.full_name || selectedRoute.driver?.login || "—" }}</p>
      <p><strong>ТС:</strong> {{ selectedRoute.number_auto || "—" }}</p>
      <h3>Точки</h3>
      <ol>
        <li v-for="point in selectedRoute.points || []" :key="point.id">
          {{ point.type_point }} | {{ point.date_point }} | {{ point.place_point }} ({{ point.status }})
        </li>
      </ol>
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
}
.actions {
  display: flex;
  gap: 0.5rem;
}
.table-wrap {
  overflow-x: auto;
  border: 1px solid #374151;
  border-radius: 10px;
  background: #111827;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th,
td {
  padding: 0.55rem;
  border-bottom: 1px solid #1f2937;
  text-align: left;
  white-space: nowrap;
}
.row-actions {
  display: flex;
  gap: 0.4rem;
  align-items: center;
}
.empty {
  text-align: center;
  color: #9ca3af;
}
.error {
  color: #fca5a5;
}
.form-card {
  display: grid;
  gap: 0.55rem;
}
.detail-card {
  display: grid;
  gap: 0.35rem;
}
label {
  display: grid;
  gap: 0.3rem;
}
input,
select,
textarea {
  border-radius: 8px;
  border: 1px solid #374151;
  background: #0b1220;
  color: #fff;
  padding: 0.45rem 0.6rem;
}
</style>

