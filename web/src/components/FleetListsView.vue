<script setup lang="ts">
import { computed, ref } from "vue";

import { isValidPlate, normalizePlate, PLATE_HINT } from "../vehiclePlate";

export type FleetItem = { id: number; plate: string };

const props = defineProps<{
  vehicles: FleetItem[];
  trailers: FleetItem[];
  loading: boolean;
  saving: boolean;
  error: string;
}>();

const emit = defineEmits<{
  refresh: [];
  createVehicle: [plate: string];
  updateVehicle: [payload: { id: number; plate: string }];
  deleteVehicle: [id: number];
  createTrailer: [plate: string];
  updateTrailer: [payload: { id: number; plate: string }];
  deleteTrailer: [id: number];
}>();

const tab = ref<"vehicles" | "trailers">("vehicles");
const draft = ref("");
const editId = ref<number | null>(null);
const editPlate = ref("");
const localError = ref("");

const currentItems = computed(() => (tab.value === "vehicles" ? props.vehicles : props.trailers));

function switchTab(next: "vehicles" | "trailers"): void {
  tab.value = next;
  draft.value = "";
  editId.value = null;
  localError.value = "";
}

function submitNew(): void {
  const plate = normalizePlate(draft.value);
  if (!isValidPlate(plate)) {
    localError.value = PLATE_HINT;
    return;
  }
  localError.value = "";
  if (tab.value === "vehicles") {
    emit("createVehicle", plate);
  } else {
    emit("createTrailer", plate);
  }
  draft.value = "";
}

function startEdit(item: FleetItem): void {
  editId.value = item.id;
  editPlate.value = item.plate;
  localError.value = "";
}

function saveEdit(): void {
  if (editId.value == null) {
    return;
  }
  const plate = normalizePlate(editPlate.value);
  if (!isValidPlate(plate)) {
    localError.value = PLATE_HINT;
    return;
  }
  localError.value = "";
  if (tab.value === "vehicles") {
    emit("updateVehicle", { id: editId.value, plate });
  } else {
    emit("updateTrailer", { id: editId.value, plate });
  }
  editId.value = null;
}

function remove(item: FleetItem): void {
  if (!window.confirm(`Удалить ${item.plate}?`)) {
    return;
  }
  if (tab.value === "vehicles") {
    emit("deleteVehicle", item.id);
  } else {
    emit("deleteTrailer", item.id);
  }
}
</script>

<template>
  <section class="wrap">
    <p v-if="error || localError" class="error">{{ error || localError }}</p>
    <div class="tabs">
      <button type="button" class="tab-btn" :class="{ active: tab === 'vehicles' }" @click="switchTab('vehicles')">
        Транспорт
      </button>
      <button type="button" class="tab-btn" :class="{ active: tab === 'trailers' }" @click="switchTab('trailers')">
        Прицепы
      </button>
    </div>
    <div class="card">
      <h2>{{ tab === "vehicles" ? "Транспорт" : "Прицепы" }}</h2>
      <p class="hint">{{ PLATE_HINT }}</p>
      <div class="row">
        <input
          v-model="draft"
          class="upper"
          :placeholder="tab === 'vehicles' ? 'Госномер ТС' : 'Госномер прицепа'"
          autocapitalize="characters"
          @input="draft = normalizePlate(draft)"
        />
        <button type="button" class="primary" :disabled="saving || !draft" @click="submitNew">Добавить</button>
      </div>
      <p v-if="!currentItems.length && !loading" class="empty">Список пуст</p>
      <ul class="list">
        <li v-for="item in currentItems" :key="item.id" class="item">
          <template v-if="editId === item.id">
            <input v-model="editPlate" class="upper grow" autocapitalize="characters" @input="editPlate = normalizePlate(editPlate)" />
            <button type="button" class="secondary" :disabled="saving" @click="saveEdit">Сохранить</button>
            <button type="button" class="ghost" @click="editId = null">Отмена</button>
          </template>
          <template v-else>
            <strong>{{ item.plate }}</strong>
            <div class="item-actions">
              <button type="button" class="icon-btn" :disabled="saving" title="Изменить" aria-label="Изменить" @click="startEdit(item)">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    fill="currentColor"
                    d="M4 17.25V20h2.75L17.81 8.94l-2.75-2.75L4 17.25Zm16.71-9.96a.996.996 0 0 0 0-1.41l-2.59-2.59a.996.996 0 0 0-1.41 0l-1.83 1.83 4 4 1.83-1.83Z"
                  />
                </svg>
              </button>
              <button type="button" class="icon-btn danger" :disabled="saving" title="Удалить" aria-label="Удалить" @click="remove(item)">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    fill="currentColor"
                    d="M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12ZM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4Z"
                  />
                </svg>
              </button>
            </div>
          </template>
        </li>
      </ul>
    </div>
  </section>
</template>

<style scoped>
.wrap {
  max-width: 720px;
  width: 100%;
  margin: 0 auto;
  display: grid;
  gap: 0.75rem;
}
.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  align-items: center;
}
.tab-btn {
  width: auto;
  border: 1px solid var(--border-strong);
  border-radius: 999px;
  background: var(--surface);
  color: #dbeafe;
  padding: 0.45rem 0.8rem;
}
.tab-btn.active {
  background: var(--primary-strong);
  border-color: #60a5fa;
}
.card {
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 0.95rem;
  background: rgba(15, 23, 42, 0.72);
}
h2 {
  margin: 0 0 0.35rem;
  font-size: 0.78rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-label);
}
.hint,
.empty {
  color: var(--text-muted);
  font-size: 0.85rem;
}
.error {
  color: #fca5a5;
}
.row {
  display: flex;
  gap: 0.45rem;
  flex-wrap: wrap;
  margin: 0.6rem 0;
}
.row input {
  flex: 1 1 12rem;
}
input {
  border-radius: 10px;
  border: 1px solid var(--border-strong);
  background: var(--bg-elevated);
  color: var(--text);
  padding: 0.5rem 0.62rem;
}
.upper {
  text-transform: uppercase;
}
.grow {
  flex: 1 1 10rem;
}
.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.4rem;
}
.item {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  align-items: center;
  padding: 0.55rem 0.2rem;
  border-bottom: 1px solid var(--border);
}
.item strong {
  flex: 1 1 8rem;
  letter-spacing: 0.04em;
}
.item-actions {
  display: flex;
  gap: 0.3rem;
}
.icon-btn {
  width: 2.25rem;
  height: 2.25rem;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  border: 1px solid var(--border-strong);
  background: var(--surface);
  color: #bfdbfe;
}
.icon-btn svg {
  width: 1.05rem;
  height: 1.05rem;
}
.icon-btn.danger {
  color: #fca5a5;
  border-color: rgba(248, 113, 113, 0.35);
  background: rgba(127, 29, 29, 0.25);
}
.primary {
  border: none;
  border-radius: 10px;
  background: var(--success-strong);
  color: #fff;
  padding: 0.45rem 0.75rem;
}
.secondary {
  border: none;
  border-radius: 10px;
  background: var(--primary);
  color: #fff;
  padding: 0.4rem 0.7rem;
}
.ghost {
  border: 1px solid var(--border-strong);
  border-radius: 10px;
  background: transparent;
  color: #cbd5e1;
  padding: 0.4rem 0.7rem;
}
</style>
