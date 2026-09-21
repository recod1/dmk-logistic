<script setup lang="ts">
import { onMounted, ref, watch } from "vue";

import type { SalaryRecord } from "../api";
import { salaryCommentText, salaryStatusKey, salaryStatusLabel } from "../salaryDisplay";

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
    <button class="ghost back" type="button" @click="emit('back')">← Назад</button>
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
          <span class="t2">{{ r.total.toFixed(2) }} ₽</span>
          <span class="status" :class="`status--${salaryStatusKey(r.status_driver)}`">{{ salaryStatusLabel(r.status_driver) }}</span>
          <span v-if="salaryCommentText(r.comment_driver)" class="comment">{{ salaryCommentText(r.comment_driver) }}</span>
        </button>
      </div>
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
  min-width: 0;
}
h2 {
  margin: 0 0 0.35rem;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-label);
}
.card {
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 0.95rem;
  background: rgba(15, 23, 42, 0.72);
  box-shadow: var(--shadow-sm);
  min-width: 0;
}
.row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.5rem;
}
.field {
  display: grid;
  gap: 0.2rem;
  font-size: 0.85rem;
  min-width: 0;
}
input {
  width: 100%;
  min-width: 0;
  border-radius: 10px;
  border: 1px solid var(--border-strong);
  background: var(--bg-elevated);
  color: #fff;
  padding: 0.5rem 0.6rem;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-top: 0.5rem;
}
.list {
  display: grid;
  gap: 0.4rem;
}
.row-item {
  text-align: left;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 0.65rem 0.75rem;
  background: rgba(2, 6, 23, 0.45);
  color: #e2e8f0;
  display: grid;
  gap: 0.15rem;
}
.t1 {
  font-weight: 650;
}
.t2 {
  font-size: 0.85rem;
  color: var(--text-muted);
}
.status {
  display: inline-flex;
  width: fit-content;
  margin-top: 0.1rem;
  padding: 0.12rem 0.45rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 650;
}
.status--pending {
  background: rgba(245, 158, 11, 0.16);
  color: #fcd34d;
}
.status--commented {
  background: rgba(56, 189, 248, 0.16);
  color: #7dd3fc;
}
.status--confirmed {
  background: rgba(34, 197, 94, 0.16);
  color: #86efac;
}
.comment {
  font-size: 0.82rem;
  color: #fde68a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hint {
  margin: 0 0 0.5rem;
  color: var(--text-muted);
  font-size: 0.88rem;
}
.ghost,
.secondary,
.primary {
  min-height: 40px;
  border-radius: 10px;
}
.ghost {
  border: 1px solid var(--border-strong);
  background: transparent;
  color: #cbd5e1;
  padding: 0.35rem 0.55rem;
}
.secondary {
  border: none;
  background: var(--primary);
  color: #fff;
  padding: 0.35rem 0.55rem;
}
.primary {
  border: none;
  background: var(--success-strong);
  color: #fff;
  padding: 0.35rem 0.55rem;
  font-weight: 650;
}
.error {
  color: #fca5a5;
  margin: 0;
}
@media (max-width: 420px) {
  .row {
    grid-template-columns: 1fr;
  }
}
</style>
