<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from "vue";

import { formatListStatusWithFact, formatPointSchedule, listPointStatusLabel } from "../status";
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
  point_note: string;
};

const props = defineProps<{
  routes: AdminRoute[];
  drivers: DriverOption[];
  logistics?: DriverOption[];
  logisticsContacts?: Array<{ name: string; phone: string }>;
  currentUserId?: number;
  loading: boolean;
  error: string;
  unreadByRoute?: Record<string, number>;
  initialFilters?: RouteSearchFilters;
}>();

const emit = defineEmits<{
  refresh: [filters?: RouteSearchFilters];
  create: [
    payload: {
      route_id: string;
      driver_fio: string;
      driver_user_id?: number | null;
      created_by_user_id?: number | null;
      number_auto?: string;
      temperature?: string;
      dispatcher_contacts?: string;
      registration_number?: string;
      trailer_number?: string;
      points: AdminRoutePointPayload[];
    }
  ];
  createOnec: [payload: { raw_text: string; driver_user_id?: number | null; number_auto?: string; trailer_number?: string }];
  selectRoute: [routeId: string];
}>();

const statusTabs: Array<{ label: string; value: RouteWorkflowStatus }> = [
  { label: "Не приняты", value: "new" },
  { label: "В процессе", value: "process" },
  { label: "Завершены", value: "success" },
  { label: "Отменён", value: "cancelled" }
];

const showCreate = ref(false);
const showCreateOnec = ref(false);
const createCardEl = ref<HTMLElement | null>(null);
const searchOpen = ref(
  Boolean(
    props.initialFilters?.route_id || props.initialFilters?.number_auto || props.initialFilters?.driver_query
  )
);
const filters = reactive({
  route_id: props.initialFilters?.route_id || "",
  number_auto: props.initialFilters?.number_auto || "",
  driver_query: props.initialFilters?.driver_query || "",
  status: props.initialFilters?.status || "process"
});

const selectedTabLabel = computed(() => {
  const tab = statusTabs.find((item) => item.value === filters.status);
  return tab?.label ?? "Все";
});

const filteredTitle = computed(() => `Рейсы (${selectedTabLabel.value}) — ${props.routes.length}`);
const isNewTab = computed(() => filters.status === "new");
const isProcessTab = computed(() => filters.status === "process");
const tableColspan = computed(() => 4 + (isNewTab.value ? 1 : 0) + (isProcessTab.value ? 1 : 0));

function unreadCount(routeId: string): number {
  return props.unreadByRoute?.[routeId] ?? 0;
}

function currentListPoint(route: AdminRoute): {
  status?: string | null;
  place?: string | null;
  name?: string | null;
  type?: string | null;
  date?: string | null;
  time?: string | null;
} | null {
  if (
    route.active_point_status ||
    route.active_point_place ||
    route.active_point_name ||
    route.active_point_date ||
    route.active_point_time
  ) {
    return {
      status: route.active_point_status,
      place: route.active_point_place,
      name: route.active_point_name,
      type: route.active_point_type,
      date: route.active_point_date,
      time: route.active_point_time
    };
  }
  const points = route.points || [];
  const current = points.find((point) => point.status !== "docs" && point.status !== "success") ?? points[points.length - 1];
  if (!current) {
    return null;
  }
  return {
    status: current.status,
    place: current.place_point,
    name: current.point_name,
    type: current.type_point,
    date: current.date_point,
    time: current.point_time
  };
}

function routeListStatus(route: AdminRoute): string {
  if (route.status === "process") {
    const stage = listPointStatusLabel(currentListPoint(route)?.status);
    return formatListStatusWithFact(stage || STATUS_LABELS.process, route.active_point_fact_time);
  }
  return STATUS_LABELS[route.status] ?? route.status;
}

function routeListPointName(route: AdminRoute): string {
  const current = currentListPoint(route);
  const place = (current?.place || "").trim();
  const name = (current?.name || "").trim();
  return place || name || "—";
}

function routeListPointSchedule(route: AdminRoute): string {
  const current = currentListPoint(route);
  return formatPointSchedule(current?.type, current?.date, current?.time);
}

function phoneReceiptLabel(route: AdminRoute): string {
  if (!route.driver?.id) {
    return "—";
  }
  return route.driver_received_at ? "Получен" : "Не получен";
}

function phoneReceiptHint(route: AdminRoute): string {
  if (!route.driver?.id) {
    return "Водитель не назначен";
  }
  if (!route.driver_received_at) {
    return "Водитель ещё не получил рейс на телефон";
  }
  try {
    return `Скачан на телефон: ${new Date(route.driver_received_at).toLocaleString()}`;
  } catch {
    return "Рейс скачан приложением на телефоне водителя";
  }
}

function upperOnly(value: string): string {
  return (value || "").toUpperCase();
}

const createForm = reactive({
  route_id: "",
  driver_user_id: 0,
  created_by_user_id: 0,
  number_auto: "",
  temperature: "",
  dispatcher_contacts: "",
  registration_number: "",
  trailer_number: "",
  points: [] as PointForm[]
});

const onecForm = reactive({
  raw_text: "",
  driver_user_id: 0,
  number_auto: "",
  trailer_number: ""
});

const createDriverQuery = ref("");
const createDriverOpen = ref(false);
const onecDriverQuery = ref("");
const onecDriverOpen = ref(false);

function driverMatches(query: string): DriverOption[] {
  const q = query.trim().toLowerCase();
  const list = props.drivers;
  if (!q) {
    return list.slice(0, 12);
  }
  return list
    .filter((driver) => {
      const name = (driver.full_name || "").toLowerCase();
      const login = (driver.login || "").toLowerCase();
      return name.includes(q) || login.includes(q);
    })
    .slice(0, 12);
}

const createDriverMatches = computed(() => driverMatches(createDriverQuery.value));
const onecDriverMatches = computed(() => driverMatches(onecDriverQuery.value));

function pickCreateDriver(driver: DriverOption): void {
  createForm.driver_user_id = driver.id;
  createDriverQuery.value = driver.full_name || driver.login;
  createDriverOpen.value = false;
}

function pickOnecDriver(driver: DriverOption): void {
  onecForm.driver_user_id = driver.id;
  onecDriverQuery.value = driver.full_name || driver.login;
  onecDriverOpen.value = false;
}

function clearOnecDriver(): void {
  onecForm.driver_user_id = 0;
  onecDriverQuery.value = "";
  onecDriverOpen.value = false;
}

function makeEmptyPoint(): PointForm {
  return {
    type_point: "loading",
    place_point: "",
    date_point: "",
    point_time: "",
    point_note: ""
  };
}

function toPointPayload(points: PointForm[]): AdminRoutePointPayload[] {
  return points.map((point, index) => ({
    type_point: point.type_point || "loading",
    place_point: point.place_point.trim(),
    date_point: point.date_point.trim(),
    point_time: point.point_time.trim(),
    point_note: point.point_note.trim(),
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

function scrollCreateCardIntoView(): void {
  void nextTick(() => {
    createCardEl.value?.scrollIntoView({ block: "start", behavior: "smooth" });
  });
}

function defaultContactsText(): string {
  const items = (props.logisticsContacts ?? []).filter((item) => (item.name || item.phone || "").trim());
  if (!items.length) {
    return "";
  }
  return items.map((item) => `${(item.name || "").trim()} ${(item.phone || "").trim()}`.trim()).join("; ");
}

function openCreate(): void {
  showCreate.value = true;
  showCreateOnec.value = false;
  createForm.route_id = "";
  createForm.driver_user_id = 0;
  createForm.created_by_user_id = props.currentUserId || 0;
  createDriverQuery.value = "";
  createDriverOpen.value = false;
  createForm.number_auto = "";
  createForm.temperature = "";
  createForm.dispatcher_contacts = defaultContactsText();
  createForm.registration_number = "";
  createForm.trailer_number = "";
  createForm.points = [];
  scrollCreateCardIntoView();
}

function openCreateOnec(): void {
  showCreateOnec.value = true;
  showCreate.value = false;
  onecForm.raw_text = "";
  onecForm.driver_user_id = 0;
  onecDriverQuery.value = "";
  onecDriverOpen.value = false;
  onecForm.number_auto = "";
  onecForm.trailer_number = "";
  scrollCreateCardIntoView();
}

function guessOnecField(raw: string, keys: string[]): string {
  const lines = (raw || "")
    .split(/\r?\n/g)
    .map((l) => l.trim())
    .filter(Boolean);
  const lowKeys = keys.map((k) => k.toLowerCase());
  for (const line of lines) {
    const lower = line.toLowerCase();
    const hit = lowKeys.find((k) => lower.includes(k));
    if (!hit) continue;
    const parts = line.split(":", 2);
    if (parts.length === 2) {
      return parts[1].trim();
    }
    const idx = lower.indexOf(hit);
    if (idx >= 0) {
      return line.slice(idx + hit.length).trim().replace(/^[-–—\s:]+/, "").trim();
    }
  }
  return "";
}

function fillFromOnecText(): void {
  const raw = onecForm.raw_text || "";
  if (!onecForm.number_auto.trim()) {
    onecForm.number_auto = guessOnecField(raw, ["номер тс", "тс", "номер авто"]).toUpperCase();
  }
  if (!onecForm.trailer_number.trim()) {
    onecForm.trailer_number = guessOnecField(raw, ["номер прицепа", "прицеп"]).toUpperCase();
  }
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
  const driver = props.drivers.find((d) => d.id === createForm.driver_user_id) || null;
  const driverFio = (driver?.full_name || driver?.login || "").trim();
  if (!driverFio) {
    return;
  }
  emit("create", {
    route_id: createForm.route_id.trim(),
    driver_fio: driverFio,
    driver_user_id: createForm.driver_user_id,
    created_by_user_id: createForm.created_by_user_id || undefined,
    number_auto: createForm.number_auto.trim(),
    temperature: createForm.temperature.trim(),
    dispatcher_contacts: createForm.dispatcher_contacts.trim(),
    registration_number: createForm.registration_number.trim(),
    trailer_number: createForm.trailer_number.trim(),
    points: toPointPayload(createForm.points).filter((point) => point.place_point && point.date_point)
  });
  showCreate.value = false;
}

function submitCreateOnec(): void {
  const raw = onecForm.raw_text.trim();
  if (!raw) {
    return;
  }
  emit("createOnec", {
    raw_text: raw,
    driver_user_id: onecForm.driver_user_id || null,
    number_auto: onecForm.number_auto.trim() || undefined,
    trailer_number: onecForm.trailer_number.trim() || undefined
  });
  showCreateOnec.value = false;
}

onMounted(() => {
  doSearch();
});
</script>

<template>
  <section class="admin-routes-page">
    <div v-if="!showCreate && !showCreateOnec" class="create-toggles">
      <button class="ghost create-toggle" :disabled="loading" @click="openCreate">+ Создать рейс</button>
      <button class="ghost create-toggle" :disabled="loading" @click="openCreateOnec">
        + Создать из 1С
      </button>
    </div>

    <section v-if="!showCreate && !showCreateOnec" class="card">
      <h2>Выберите статус</h2>
      <div class="tabs desktop-status">
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
      <label class="mobile-status">
        Статус
        <select :value="filters.status" @change="setStatusTab(($event.target as HTMLSelectElement).value)">
          <option v-for="tab in statusTabs" :key="tab.value" :value="tab.value">{{ tab.label }}</option>
        </select>
      </label>
    </section>

    <section v-if="!showCreate && !showCreateOnec" class="card filters-card">
      <div class="filters-head">
        <h2>{{ filteredTitle }}</h2>
        <button class="ghost search-toggle" type="button" @click="searchOpen = !searchOpen">
          {{ searchOpen ? "Скрыть поиск" : "Поиск по рейсу" }}
        </button>
      </div>
      <div class="filters-grid" :class="{ open: searchOpen }">
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
          <input
            v-model="filters.number_auto"
            class="upper"
            autocapitalize="characters"
            placeholder="А123ВС777"
            @input="(e) => (filters.number_auto = upperOnly((e.target as HTMLInputElement).value))"
          />
        </label>
        <div class="apply-wrap">
          <button class="secondary" type="button" :disabled="loading" @click="doSearch">Применить</button>
        </div>
      </div>
      <p v-if="error" class="error">{{ error }}</p>

      <div class="routes-cards" role="list">
        <button
          v-for="r in routes"
          :key="r.id"
          type="button"
          class="route-card-mobile"
          role="listitem"
          @click="emit('selectRoute', r.id)"
        >
          <span class="card-line strong">
            {{ r.id }}
            <span v-if="unreadCount(r.id) > 0" class="chat-dot" :title="`Новых сообщений: ${unreadCount(r.id)}`" />
          </span>
          <span class="card-line"
            ><span class="lbl">Водитель:</span> {{ r.driver?.full_name || r.driver?.login || "—" }}</span
          >
          <span class="card-line"><span class="lbl">ТС:</span> {{ r.number_auto || "—" }}</span>
          <span class="card-line"
            ><span class="lbl">Статус:</span> {{ routeListStatus(r) }}</span
          >
          <span v-if="isProcessTab" class="card-line"
            ><span class="lbl">Точка:</span> {{ routeListPointName(r) }}</span
          >
          <span v-if="isProcessTab && routeListPointSchedule(r)" class="card-line"
            ><span class="lbl">План:</span> {{ routeListPointSchedule(r) }}</span
          >
          <span v-if="isNewTab" class="card-line"
            ><span class="lbl">На телефоне:</span>
            <span :title="phoneReceiptHint(r)">{{ phoneReceiptLabel(r) }}</span></span
          >
        </button>
        <p v-if="!routes.length" class="empty cards-empty">Рейсы не найдены</p>
      </div>

      <div class="table-wrap table-wrap-desktop">
        <table>
          <thead>
            <tr>
              <th>№ рейса</th>
              <th>Водитель</th>
              <th>ТС</th>
              <th>Статус</th>
              <th v-if="isProcessTab">Точка</th>
              <th v-if="isNewTab">На телефоне</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="route in routes" :key="route.id" @click="emit('selectRoute', route.id)">
              <td>
                <span class="route-id">
                  {{ route.id }}
                  <span v-if="unreadCount(route.id) > 0" class="chat-dot" :title="`Новых сообщений: ${unreadCount(route.id)}`" />
                </span>
              </td>
              <td>{{ route.driver?.full_name || route.driver?.login || "—" }}</td>
              <td>{{ route.number_auto || "—" }}</td>
              <td>{{ routeListStatus(route) }}</td>
              <td v-if="isProcessTab">
                <div>{{ routeListPointName(route) }}</div>
                <div v-if="routeListPointSchedule(route)" class="point-when">{{ routeListPointSchedule(route) }}</div>
              </td>
              <td v-if="isNewTab" :title="phoneReceiptHint(route)">{{ phoneReceiptLabel(route) }}</td>
            </tr>
            <tr v-if="!routes.length">
              <td :colspan="tableColspan" class="empty">Рейсы не найдены</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="showCreateOnec" ref="createCardEl" class="card create-card">
      <h2>Создать рейс из 1С</h2>
      <label class="driver-search">
        Водитель (если в тексте не найден / не однозначно)
        <input
          v-model="onecDriverQuery"
          placeholder="Начните вводить ФИО или оставьте пустым для авто"
          autocomplete="off"
          @focus="onecDriverOpen = true"
        />
        <p v-if="onecForm.driver_user_id" class="picked">Выбран: {{ onecDriverQuery }}</p>
        <div v-if="onecDriverOpen" class="driver-suggest">
          <button type="button" class="suggest-item" @click="clearOnecDriver">Авто (по ФИО из текста)</button>
          <button
            v-for="driver in onecDriverMatches"
            :key="driver.id"
            type="button"
            class="suggest-item"
            @click="pickOnecDriver(driver)"
          >
            {{ driver.full_name || driver.login }}
          </button>
        </div>
      </label>
      <div class="create-grid onec-grid">
        <label>
          Номер ТС
          <input v-model="onecForm.number_auto" class="upper" autocapitalize="characters" />
        </label>
        <label>
          Номер прицепа
          <input v-model="onecForm.trailer_number" class="upper" autocapitalize="characters" />
        </label>
        <div class="onec-fill">
          <button class="secondary" type="button" @click="fillFromOnecText">Взять из текста</button>
        </div>
      </div>
      <label>
        Текст 1С
        <textarea v-model="onecForm.raw_text" rows="6" placeholder="Вставьте сообщение 1С целиком" />
      </label>
      <div class="actions">
        <button class="primary" type="button" @click="submitCreateOnec">Создать</button>
        <button class="ghost" type="button" @click="showCreateOnec = false">Отмена</button>
      </div>
    </section>

    <section v-if="showCreate" ref="createCardEl" class="card create-card">
      <h2>Создать рейс</h2>
      <div class="create-grid">
        <label>
          ID рейса
          <input v-model="createForm.route_id" placeholder="R-2026-0001" />
        </label>
        <label class="driver-search">
          Водитель
          <input
            v-model="createDriverQuery"
            placeholder="Начните вводить ФИО"
            autocomplete="off"
            @focus="createDriverOpen = true"
          />
          <p v-if="createForm.driver_user_id" class="picked">Выбран: {{ createDriverQuery }}</p>
          <div v-if="createDriverOpen && createDriverMatches.length" class="driver-suggest">
            <button
              v-for="driver in createDriverMatches"
              :key="driver.id"
              type="button"
              class="suggest-item"
              @click="pickCreateDriver(driver)"
            >
              {{ driver.full_name || driver.login }}
            </button>
          </div>
        </label>
        <label>
          Логист
          <select v-model.number="createForm.created_by_user_id">
            <option :value="0">Не выбран</option>
            <option v-for="person in logistics || []" :key="person.id" :value="person.id">
              {{ person.full_name || person.login }}
            </option>
          </select>
        </label>
        <label>
          Номер авто
          <input
            v-model="createForm.number_auto"
            class="upper"
            autocapitalize="characters"
            @input="(e) => (createForm.number_auto = upperOnly((e.target as HTMLInputElement).value))"
          />
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
          <input
            v-model="createForm.trailer_number"
            class="upper"
            autocapitalize="characters"
            @input="(e) => (createForm.trailer_number = upperOnly((e.target as HTMLInputElement).value))"
          />
        </label>
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
          <label class="full">
            Примечание
            <textarea v-model="point.point_note" rows="2" />
          </label>
          <label>
            Дата
            <input v-model="point.date_point" type="date" lang="ru" />
          </label>
          <label>
            Время
            <input v-model="point.point_time" type="time" step="60" lang="ru" />
          </label>
        </div>
      </article>
      <div class="actions">
        <button class="secondary" type="button" @click="addCreatePoint">Добавить точку</button>
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
  width: 100%;
  max-width: 1200px;
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
.card > h2 {
  margin: 0 0 0.55rem;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-label);
}
.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.tab-btn {
  width: auto;
  border: 1px solid var(--border-strong);
  border-radius: 999px;
  background: var(--surface);
  color: #dbeafe;
  padding: 0.48rem 0.8rem;
}
.tab-btn.active {
  background: var(--primary-strong);
  border-color: #60a5fa;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.22);
}
.filters-grid {
  display: grid;
  gap: 0.6rem;
}
.filters-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.filters-head h2 {
  margin: 0;
}
.search-toggle,
.mobile-status {
  display: none;
}
.apply-wrap {
  display: flex;
  align-items: end;
}
.routes-cards {
  display: none;
  margin-top: 0.75rem;
}
.route-card-mobile {
  display: grid;
  gap: 0.28rem;
  width: 100%;
  text-align: left;
  padding: 0.75rem 0.85rem;
  border-radius: 12px;
  border: 1px solid #243043;
  background: rgba(2, 6, 23, 0.55);
  color: #e2e8f0;
  cursor: pointer;
  font: inherit;
}
.route-card-mobile:active {
  background: rgba(79, 70, 229, 0.18);
}
.card-line {
  font-size: 0.92rem;
  line-height: 1.4;
  word-break: break-word;
  color: var(--text-heading);
}
.card-line.strong {
  font-weight: 700;
  color: #f8fafc;
  font-size: 1rem;
}
.route-id {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}
.chat-dot {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 999px;
  background: #22c55e;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.22);
  vertical-align: middle;
  animation: route-unread-pulse 1.8s ease-in-out infinite;
}
@keyframes route-unread-pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.2);
    opacity: 0.7;
  }
}
.card-line .lbl {
  color: var(--text-label);
  margin-right: 0.3rem;
  font-size: 0.75rem;
  font-weight: 650;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}
.cards-empty {
  margin: 0.5rem 0 0;
}
.table-wrap {
  margin-top: 0.75rem;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  max-width: 100%;
  border: 1px solid #243043;
  border-radius: 12px;
}
table {
  width: 100%;
  min-width: 520px;
  border-collapse: collapse;
}
th,
td {
  text-align: left;
  padding: 0.65rem;
  border-bottom: 1px solid #243043;
}
.point-when {
  margin-top: 0.2rem;
  color: var(--text-muted);
  font-size: 0.8rem;
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
.create-card textarea {
  min-height: 7.5rem;
  resize: vertical;
}
@media (max-width: 760px) {
  .create-card textarea {
    min-height: 5.5rem;
    max-height: 12rem;
  }
  .create-card .actions {
    position: sticky;
    bottom: 0;
    z-index: 3;
    margin: 0.35rem -1rem -1rem;
    padding: 0.7rem 1rem 1rem;
    background: linear-gradient(180deg, rgba(2, 6, 23, 0), rgba(2, 6, 23, 0.96) 32%, rgba(2, 6, 23, 0.98));
  }
}
.create-toggles {
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
  min-width: 0;
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
@media (max-width: 760px) {
  .desktop-status {
    display: none;
  }
  .mobile-status,
  .search-toggle {
    display: grid;
  }
  .search-toggle {
    display: inline-flex;
    align-items: center;
    width: auto;
  }
  .filters-grid {
    display: none;
  }
  .filters-grid.open {
    display: grid;
    margin-top: 0.65rem;
  }
  .routes-cards {
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
  }
  .table-wrap-desktop {
    display: none;
  }
  .filters-card h2 {
    font-size: 1rem;
    line-height: 1.35;
  }
}
@media (max-width: 640px) {
  .tabs:not(.desktop-status) {
    flex-direction: column;
  }
  .tab-btn {
    width: 100%;
    text-align: center;
  }
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

.driver-search {
  position: relative;
}
.picked {
  margin: 0.15rem 0 0;
  color: #86efac;
  font-size: 0.82rem;
}
.driver-suggest {
  position: absolute;
  z-index: 5;
  left: 0;
  right: 0;
  top: calc(100% + 4px);
  max-height: 220px;
  overflow: auto;
  border: 1px solid #334155;
  border-radius: 10px;
  background: #0b1220;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.35);
}
.suggest-item {
  width: 100%;
  text-align: left;
  background: transparent;
  border-radius: 0;
  border-bottom: 1px solid #1e293b;
  color: #e2e8f0;
}
.suggest-item:last-child {
  border-bottom: none;
}
.suggest-item:hover,
.suggest-item:focus {
  background: #1e293b;
}
.onec-grid {
  margin-top: 0.35rem;
  margin-bottom: 0.35rem;
}
.onec-fill {
  display: flex;
  align-items: end;
}
</style>

