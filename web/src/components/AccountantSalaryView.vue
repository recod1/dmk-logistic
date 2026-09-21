<script setup lang="ts">
import { ref } from "vue";

import type { SalaryRecord } from "../api";
import { salaryCommentText, salaryStatusKey, salaryStatusLabel } from "../salaryDisplay";

const props = defineProps<{
  drivers: Array<{ id: number; login: string; full_name: string | null; legacy_tg_id: string | null }>;
  items: SalaryRecord[];
  selectedDriver: { id: number; login: string; full_name: string | null } | null;
  loading: boolean;
  saving: boolean;
  error: string;
}>();

const emit = defineEmits<{
  back: [];
  search: [q: string];
  pickDriver: [id: number];
  refreshList: [dateFrom?: string, dateTo?: string];
  create: [payload: { driver_user_id: number; salary_line: string }];
  select: [row: SalaryRecord];
  exportCsv: [dateFrom: string, dateTo: string];
}>();

const q = ref("");
const salaryLine = ref("");
const dateFrom = ref("");
const dateTo = ref("");

const help =
  "37 значений через пробел, как в боте:\nдата г/мг/рд/пр оклад сутки загр2р шаттл загр/выгр дт возврат доп_шаттл доп_точка азс паллет_гипер паллет_метро паллет_ашан 3т 3.5т 5т 10т 12т 12.5т пробег комп_связи стаж 10% премия удержать возмещение др без_сут_др_прем_стажа в_день итого адрес_загр адрес_выгр транспорт прицеп №рейса";

function applyMonth(): void {
  const d = new Date();
  const y = d.getFullYear();
  const m = d.getMonth();
  const pad = (n: number) => String(n).padStart(2, "0");
  const last = new Date(y, m + 1, 0).getDate();
  dateFrom.value = `01.${pad(m + 1)}.${y}`;
  dateTo.value = `${pad(last)}.${pad(m + 1)}.${y}`;
  emit("refreshList", dateFrom.value, dateTo.value);
}

function submit(): void {
  if (!props.selectedDriver) return;
  emit("create", { driver_user_id: props.selectedDriver.id, salary_line: salaryLine.value.trim() });
}

function doExport(): void {
  if (!dateFrom.value.trim() || !dateTo.value.trim()) {
    return;
  }
  emit("exportCsv", dateFrom.value.trim(), dateTo.value.trim());
}
</script>

<template>
  <section class="wrap">
    <button class="ghost back" type="button" @click="emit('back')">← Назад</button>
    <p v-if="error" class="error">{{ error }}</p>
    <div class="card">
      <h2>Водитель</h2>
      <div class="row">
        <input v-model="q" placeholder="ФИО или логин" @keyup.enter="emit('search', q.trim())" />
        <button type="button" class="secondary" @click="emit('search', q.trim())">Найти</button>
      </div>
      <div v-if="drivers.length" class="drivers">
        <button v-for="d in drivers" :key="d.id" type="button" class="d-btn" @click="emit('pickDriver', d.id)">
          {{ d.full_name || d.login }} <span class="meta">#{{ d.id }}</span>
        </button>
      </div>
      <p v-if="selectedDriver" class="picked">Выбран: {{ selectedDriver.full_name || selectedDriver.login }} (#{{ selectedDriver.id }})</p>
    </div>
    <div v-if="selectedDriver" class="card">
      <h2>Новый расчёт</h2>
      <p class="hint">{{ help }}</p>
      <textarea v-model="salaryLine" rows="4" class="ta" placeholder="Вставьте строку из 37 значений…" />
      <button type="button" class="primary" :disabled="saving || !salaryLine.trim()" @click="submit">Сохранить расчёт</button>
    </div>
    <div v-if="selectedDriver" class="card">
      <h2>Расчёты водителя</h2>
      <div class="period">
        <input v-model="dateFrom" placeholder="дд.мм.гггг с" />
        <input v-model="dateTo" placeholder="дд.мм.гггг по" />
        <div class="period-actions">
          <button type="button" class="ghost" @click="applyMonth">Месяц</button>
          <button type="button" class="secondary" :disabled="loading" @click="emit('refreshList', dateFrom || undefined, dateTo || undefined)">
            Загрузить
          </button>
          <button type="button" class="primary" :disabled="!dateFrom || !dateTo" @click="doExport">CSV за период</button>
        </div>
      </div>
      <div class="list">
        <button v-for="r in items" :key="r.id" type="button" class="row-item" @click="emit('select', r)">
          <span class="t1">#{{ r.id }} · {{ r.date_salary }}</span>
          <span class="t2">{{ r.total.toFixed(2) }} ₽</span>
          <span class="status" :class="`status--${salaryStatusKey(r.status_driver)}`">{{ salaryStatusLabel(r.status_driver) }}</span>
          <span v-if="salaryCommentText(r.comment_driver)" class="comment">Комментарий: {{ salaryCommentText(r.comment_driver) }}</span>
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.wrap {
  max-width: 880px;
  width: 100%;
  margin: 0 auto;
  display: grid;
  gap: 0.75rem;
  min-width: 0;
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
h1 {
  margin: 0;
  font-size: 1.05rem;
}
h2 {
  margin: 0 0 0.4rem;
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
}
.row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  align-items: center;
  min-width: 0;
}
.row input {
  flex: 1 1 12rem;
  min-width: 0;
}
input {
  width: 100%;
  border-radius: 8px;
  border: 1px solid #334155;
  background: #0b1220;
  color: #fff;
  padding: 0.45rem 0.55rem;
  min-width: 0;
}
.period {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.45rem;
}
.period-actions {
  grid-column: 1 / -1;
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}
.ta {
  width: 100%;
  border-radius: 8px;
  border: 1px solid #334155;
  background: #0b1220;
  color: #e2e8f0;
  padding: 0.5rem;
  margin: 0.5rem 0;
  font-family: ui-monospace, monospace;
  font-size: 0.82rem;
}
.ta + .primary {
  margin-top: 0.35rem;
}
.drivers {
  display: grid;
  gap: 0.35rem;
  margin-top: 0.5rem;
}
.d-btn {
  text-align: left;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 0.45rem 0.55rem;
  background: rgba(2, 6, 23, 0.45);
  color: #e2e8f0;
}
.meta {
  color: #94a3b8;
  font-size: 0.85rem;
}
.picked {
  margin: 0.5rem 0 0;
  color: #a5b4fc;
  font-weight: 600;
}
.list {
  display: grid;
  gap: 0.35rem;
  margin-top: 0.5rem;
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
.status {
  display: inline-flex;
  width: fit-content;
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
  white-space: pre-wrap;
  color: #94a3b8;
  font-size: 0.78rem;
  margin: 0 0 0.35rem;
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
  padding: 0.45rem 0.65rem;
}
.error {
  color: #fca5a5;
}
@media (max-width: 420px) {
  .period {
    grid-template-columns: 1fr;
  }
}
</style>
