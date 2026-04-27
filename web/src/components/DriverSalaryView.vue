<script setup lang="ts">
import { onMounted, ref, watch } from "vue";

import type { SalaryRecord } from "../api";

const props = defineProps<{
  items: SalaryRecord[];
  loading: boolean;
  error: string;
  initialFrom?: string;
  initialTo?: string;
}>();

const emit = defineEmits<{
  back: [];
  refresh: [dateFrom?: string, dateTo?: string];
  select: [row: SalaryRecord];
  exportCsv: [dateFrom: string, dateTo: string];
}>();

const dateFrom = ref("");
const dateTo = ref("");

function applyCurrentMonth(): void {
  const d = new Date();
  const y = d.getFullYear();
  const m = d.getMonth();
  const pad = (n: number) => String(n).padStart(2, "0");
  const last = new Date(y, m + 1, 0).getDate();
  dateFrom.value = `01.${pad(m + 1)}.${y}`;
  dateTo.value = `${pad(last)}.${pad(m + 1)}.${y}`;
  emit("refresh", dateFrom.value, dateTo.value);
}

function doRefresh(): void {
  emit("refresh", dateFrom.value.trim() || undefined, dateTo.value.trim() || undefined);
}

function doExport(): void {
  if (!dateFrom.value.trim() || !dateTo.value.trim()) {
    return;
  }
  emit("exportCsv", dateFrom.value.trim(), dateTo.value.trim());
}

function syncInitial(): void {
  if (props.initialFrom) dateFrom.value = props.initialFrom;
  if (props.initialTo) dateTo.value = props.initialTo;
}

onMounted(() => {
  syncInitial();
  emit("refresh", dateFrom.value.trim() || undefined, dateTo.value.trim() || undefined);
});

watch(
  () => [props.initialFrom, props.initialTo],
  () => {
    syncInitial();
  }
);
</script>

<template>
  <section class="wrap">
    <header class="head">
      <button type="button" class="ghost" @click="emit('back')">← Назад</button>
      <h1>Зарплата</h1>
      <button type="button" class="secondary" :disabled="loading" @click="doRefresh">Обновить</button>
    </header>
    <p v-if="error" class="error">{{ error }}</p>
    <div class="card">
      <h2>Период</h2>
      <p class="hint">Даты в формате дд.мм.гггг (как в Telegram-боте).</p>
      <div class="row">
        <label class="field">
          С
          <input v-model="dateFrom" placeholder="01.01.2026" />
        </label>
        <label class="field">
          По
          <input v-model="dateTo" placeholder="31.01.2026" />
        </label>
      </div>
      <div class="actions">
        <button type="button" class="ghost" @click="applyCurrentMonth">Текущий месяц</button>
        <button type="button" class="secondary" @click="doRefresh">Показать</button>
        <button type="button" class="primary" :disabled="!dateFrom || !dateTo" @click="doExport">CSV за период</button>
      </div>
    </div>
    <div class="card">
      <h2>Расчёты</h2>
      <p v-if="!items.length && !loading" class="hint">Нет записей за выбранный период.</p>
      <div class="list">
        <button v-for="r in items" :key="r.id" type="button" class="row-item" @click="emit('select', r)">
          <span class="t1">#{{ r.id }} · {{ r.date_salary }}</span>
          <span class="t2">{{ r.total.toFixed(2) }} ₽ · {{ r.status_driver || "ожидает" }}</span>
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.wrap {
  max-width: 720px;
  margin: 0 auto;
  display: grid;
  gap: 0.75rem;
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem;
}
h1 {
  margin: 0;
  font-size: 1.05rem;
}
h2 {
  margin: 0 0 0.35rem;
  font-size: 0.95rem;
}
.card {
  border: 1px solid #243043;
  border-radius: 14px;
  padding: 0.85rem;
  background: rgba(15, 23, 42, 0.6);
}
.row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
}
.field {
  display: grid;
  gap: 0.2rem;
  font-size: 0.85rem;
}
input {
  border-radius: 8px;
  border: 1px solid #334155;
  background: #0b1220;
  color: #fff;
  padding: 0.45rem 0.55rem;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-top: 0.5rem;
}
.list {
  display: grid;
  gap: 0.35rem;
}
.row-item {
  text-align: left;
  border: 1px solid #334155;
  border-radius: 10px;
  padding: 0.55rem 0.65rem;
  background: rgba(2, 6, 23, 0.45);
  color: #e2e8f0;
  display: grid;
  gap: 0.15rem;
}
.t1 {
  font-weight: 600;
}
.t2 {
  font-size: 0.85rem;
  color: #94a3b8;
}
.hint {
  margin: 0 0 0.5rem;
  color: #94a3b8;
  font-size: 0.88rem;
}
.ghost {
  border: 1px solid #334155;
  border-radius: 8px;
  background: transparent;
  color: #cbd5e1;
  padding: 0.35rem 0.55rem;
}
.secondary {
  border: none;
  border-radius: 8px;
  background: #3b82f6;
  color: #fff;
  padding: 0.35rem 0.55rem;
}
.primary {
  border: none;
  border-radius: 8px;
  background: #16a34a;
  color: #fff;
  padding: 0.35rem 0.55rem;
}
.error {
  color: #fca5a5;
  margin: 0;
}
</style>
