<script setup lang="ts">
import { computed, ref, watch } from "vue";

import type { DriverShiftListItem } from "../types";

const props = defineProps<{
  items: DriverShiftListItem[];
  loading: boolean;
  error: string;
  statusFilter: "" | "active" | "ended";
  query: string;
  dateFrom: string;
  dateTo: string;
}>();

const emit = defineEmits<{
  refresh: [];
  updateFilters: [payload: { status: "" | "active" | "ended"; query: string; dateFrom: string; dateTo: string }];
  openShift: [shiftId: number];
}>();

const localQuery = ref(props.query);
const localFrom = ref(props.dateFrom);
const localTo = ref(props.dateTo);

watch(
  () => [props.query, props.dateFrom, props.dateTo],
  () => {
    localQuery.value = props.query;
    localFrom.value = props.dateFrom;
    localTo.value = props.dateTo;
  }
);

const tabs: Array<{ label: string; value: "" | "active" | "ended" }> = [
  { label: "Все", value: "" },
  { label: "Действующие", value: "active" },
  { label: "Законченные", value: "ended" }
];

const emptyText = computed(() => {
  if (props.loading) {
    return "Загрузка…";
  }
  return "Вахты не найдены";
});

function applySearch(): void {
  emit("updateFilters", {
    status: props.statusFilter,
    query: localQuery.value.trim(),
    dateFrom: localFrom.value.trim(),
    dateTo: localTo.value.trim()
  });
}

function setStatus(status: "" | "active" | "ended"): void {
  emit("updateFilters", {
    status,
    query: localQuery.value.trim(),
    dateFrom: localFrom.value.trim(),
    dateTo: localTo.value.trim()
  });
}
</script>

<template>
  <section class="shifts-wrap">
    <div class="head">
      <h2>Вахты</h2>
      <button class="secondary" type="button" :disabled="loading" @click="emit('refresh')">Обновить</button>
    </div>
    <div class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.value || 'all'"
        type="button"
        class="tab"
        :class="{ active: tab.value === statusFilter }"
        @click="setStatus(tab.value)"
      >
        {{ tab.label }}
      </button>
    </div>
    <form class="filters" @submit.prevent="applySearch">
      <label>
        ФИО водителя
        <input v-model="localQuery" type="search" placeholder="Поиск по ФИО" />
      </label>
      <label>
        Дата начала
        <input v-model="localFrom" type="date" />
      </label>
      <label>
        Дата окончания
        <input v-model="localTo" type="date" />
      </label>
      <button class="secondary" type="submit" :disabled="loading">Найти</button>
    </form>
    <p v-if="error" class="error">{{ error }}</p>
    <div class="list">
      <button v-for="item in items" :key="item.id" class="shift-card" type="button" @click="emit('openShift', item.id)">
        <strong>{{ item.title }}</strong>
        <small>{{ item.status === "active" ? "Действует" : "Закончена" }}</small>
      </button>
      <p v-if="!items.length" class="empty">{{ emptyText }}</p>
    </div>
  </section>
</template>

<style scoped>
.shifts-wrap {
  display: grid;
  gap: 0.85rem;
  width: 100%;
  max-width: 720px;
  margin: 0 auto;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}
h2 {
  margin: 0;
}
.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}
.tab {
  border: 1px solid var(--border-strong);
  border-radius: 999px;
  background: var(--surface);
  color: #dbeafe;
  padding: 0.35rem 0.75rem;
}
.tab.active {
  background: var(--primary-strong);
  border-color: #60a5fa;
}
.filters {
  display: grid;
  gap: 0.55rem;
}
@media (min-width: 720px) {
  .filters {
    grid-template-columns: 1.4fr 1fr 1fr auto;
    align-items: end;
  }
}
label {
  display: grid;
  gap: 0.26rem;
  font-size: 0.82rem;
  color: var(--text-muted);
}
input {
  width: 100%;
  border-radius: 10px;
  border: 1px solid #334155;
  background: #0b1220;
  color: #fff;
  padding: 0.5rem 0.62rem;
}
.list {
  display: grid;
  gap: 0.55rem;
}
.shift-card {
  text-align: left;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--surface-2, rgba(17, 24, 39, 0.88));
  color: #fff;
  padding: 0.85rem;
  display: grid;
  gap: 0.25rem;
}
.shift-card small {
  color: var(--text-muted);
}
.empty,
.error {
  margin: 0;
}
.error {
  color: #fca5a5;
}
.secondary {
  background: #3b82f6;
  color: #fff;
  border: none;
  border-radius: 10px;
  padding: 0.48rem 0.72rem;
}
</style>
