<script setup lang="ts">
import { computed, ref } from "vue";

import type { SalaryRecord } from "../api";
import { salaryCommentText, salaryStatusKey, salaryStatusLabel } from "../salaryDisplay";

const props = defineProps<{
  record: SalaryRecord;
  isDriver: boolean;
  canDelete: boolean;
  busy: boolean;
}>();

const emit = defineEmits<{
  back: [];
  confirm: [];
  comment: [text: string];
  openChat: [];
  remove: [];
}>();

const commentText = ref("");
const confirmDelete = ref(false);

type DetailRow = { label: string; value: string };

function isNonZeroNumber(v: number): boolean {
  return typeof v === "number" && Number.isFinite(v) && v !== 0;
}

function isNonEmptyText(v: string | null | undefined): boolean {
  const t = (v || "").trim();
  return Boolean(t) && t !== "0";
}

const statusKey = computed(() => salaryStatusKey(props.record.status_driver));
const statusText = computed(() => salaryStatusLabel(props.record.status_driver));
const driverComment = computed(() => salaryCommentText(props.record.comment_driver));
const isConfirmed = computed(() => statusKey.value === "confirmed");

const detailRows = computed<DetailRow[]>(() => {
  const r = props.record;
  const rows: DetailRow[] = [];
  const num = (label: string, v: number) => {
    if (isNonZeroNumber(v)) {
      rows.push({ label, value: String(v) });
    }
  };
  const text = (label: string, v: string) => {
    if (isNonEmptyText(v)) {
      rows.push({ label, value: v.trim() });
    }
  };

  text("г/мг/рд/пр", r.type_route);
  num("Оклад", r.sum_status);
  num("Суточные", r.sum_daily);
  num("Загр 2р", r.load_2_trips);
  num("Шаттл", r.calc_shuttle);
  num("Загр/выгр", r.sum_load_unload);
  num("Штора", r.sum_curtain);
  num("Возврат", r.sum_return);
  num("Доп. шаттл", r.sum_add_shuttle);
  num("Доп. точка", r.sum_add_point);
  num("АЗС", r.sum_gas_station);
  num("Паллеты гипер", r.pallets_hyper);
  num("Паллеты метро", r.pallets_metro);
  num("Паллеты ашан", r.pallets_ashan);
  num("Тариф 3", r.rate_3km);
  num("Тариф 3.5", r.rate_3_5km);
  num("Тариф 5", r.rate_5km);
  num("Тариф 10", r.rate_10km);
  num("Тариф 12", r.rate_12km);
  num("Тариф 12.5", r.rate_12_5km);
  num("Пробег", r.mileage);
  num("Комп. связи", r.sum_cell_compensation);
  num("Стаж", r.experience);
  num("10%", r.percent_10);
  num("Премия", r.sum_bonus);
  num("Удержать", r.withhold);
  num("Возмещение", r.compensation);
  num("ДР", r.dr);
  num("Без сут/ДР/прем/стажа", r.sum_without_daily_dr_bonus_exp);
  num("В день", r.sum_without_daily_dr_bonus);
  text("Адрес загрузки", r.load_address);
  text("Адрес выгрузки", r.unload_address);
  text("ТС", r.transport);
  text("Прицеп", r.trailer_number);
  text("№ рейса", r.route_number);
  return rows;
});

function submitComment(): void {
  const text = commentText.value.trim();
  if (!text) return;
  emit("comment", text);
  commentText.value = "";
}
</script>

<template>
  <section class="wrap">
    <header class="head">
      <button type="button" class="ghost" @click="emit('back')">← Назад</button>
      <h1>Расчёт #{{ record.id }}</h1>
      <button type="button" class="secondary" @click="emit('openChat')">Чат расчёта</button>
    </header>
    <div class="card">
      <p class="meta">{{ record.date_salary }}</p>
      <p class="status-banner" :class="`status-banner--${statusKey}`" role="status">
        {{ statusText }}
      </p>
      <p class="sum">Итого: {{ record.total.toFixed(2) }} ₽</p>
      <aside v-if="driverComment" class="comment-card">
        <h2>Комментарий водителя</h2>
        <p class="comment-text">{{ driverComment }}</p>
      </aside>
      <dl v-if="detailRows.length" class="grid">
        <template v-for="row in detailRows" :key="row.label">
          <dt>{{ row.label }}</dt>
          <dd>{{ row.value }}</dd>
        </template>
      </dl>
      <p v-else class="empty">Все значения равны нулю</p>
    </div>
    <div v-if="isDriver" class="card">
      <h2>Действия водителя</h2>
      <p v-if="isConfirmed" class="confirmed-note">Расчёт подтверждён. Кнопка подтверждения скрыта.</p>
      <button v-else type="button" class="primary" :disabled="busy" @click="emit('confirm')">Подтвердить расчёт</button>
      <label class="field">
        Комментарий бухгалтеру
        <textarea v-model="commentText" rows="3" placeholder="Текст комментария" />
      </label>
      <button type="button" class="secondary" :disabled="busy || !commentText.trim()" @click="submitComment">
        Отправить комментарий
      </button>
    </div>
    <div v-if="canDelete" class="card danger-card">
      <h2>Удаление</h2>
      <p class="hint">Расчёт будет удалён без возможности восстановления.</p>
      <template v-if="!confirmDelete">
        <button type="button" class="danger" :disabled="busy" @click="confirmDelete = true">Удалить расчёт</button>
      </template>
      <div v-else class="delete-confirm">
        <p class="warn">Удалить расчёт #{{ record.id }}?</p>
        <button type="button" class="ghost" :disabled="busy" @click="confirmDelete = false">Отмена</button>
        <button type="button" class="danger" :disabled="busy" @click="emit('remove')">Да, удалить</button>
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
}
.head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem;
  justify-content: space-between;
}
h1 {
  margin: 0;
  font-size: 1rem;
  flex: 1;
  text-align: center;
}
h2 {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
}
.card {
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 0.95rem;
  background: rgba(15, 23, 42, 0.72);
  box-shadow: var(--shadow-sm);
}
.meta {
  color: var(--text-muted);
  margin: 0 0 0.45rem;
}
.status-banner {
  margin: 0 0 0.65rem;
  padding: 0.55rem 0.7rem;
  border-radius: 12px;
  font-weight: 750;
  letter-spacing: -0.01em;
}
.status-banner--pending {
  background: rgba(245, 158, 11, 0.16);
  color: #fcd34d;
  border: 1px solid rgba(245, 158, 11, 0.35);
}
.status-banner--commented {
  background: rgba(56, 189, 248, 0.16);
  color: #7dd3fc;
  border: 1px solid rgba(56, 189, 248, 0.35);
}
.status-banner--confirmed {
  background: rgba(34, 197, 94, 0.18);
  color: #86efac;
  border: 1px solid rgba(34, 197, 94, 0.4);
}
.sum {
  font-size: 1.25rem;
  font-weight: 750;
  margin: 0 0 0.75rem;
  color: #fde68a;
  letter-spacing: -0.02em;
}
.comment-card {
  margin: 0 0 0.85rem;
  padding: 0.75rem 0.8rem;
  border-radius: 12px;
  background: rgba(251, 191, 36, 0.12);
  border: 1px solid rgba(251, 191, 36, 0.38);
}
.comment-card h2 {
  margin: 0 0 0.35rem;
  color: #fde68a;
  font-size: 0.82rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.comment-text {
  margin: 0;
  white-space: pre-wrap;
  color: #fff7ed;
  font-size: 0.95rem;
  line-height: 1.4;
}
.grid {
  display: grid;
  grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.2fr);
  gap: 0.5rem 0.75rem;
  font-size: 0.88rem;
  margin: 0;
}
dt {
  color: var(--text-muted);
  min-width: 0;
  overflow-wrap: anywhere;
}
dd {
  margin: 0;
  word-break: break-word;
  overflow-wrap: anywhere;
  min-width: 0;
}
.empty {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.88rem;
}
.confirmed-note {
  margin: 0 0 0.65rem;
  padding: 0.55rem 0.65rem;
  border-radius: 10px;
  background: rgba(34, 197, 94, 0.16);
  color: #86efac;
  font-weight: 650;
}
.field {
  display: grid;
  gap: 0.25rem;
  margin: 0.65rem 0 0.35rem;
  font-size: 0.88rem;
}
textarea {
  border-radius: 10px;
  border: 1px solid var(--border-strong);
  background: var(--bg-elevated);
  color: #fff;
  padding: 0.5rem;
}
.hint {
  margin: 0 0 0.5rem;
  color: var(--text-muted);
  font-size: 0.88rem;
}
.danger-card {
  border-color: rgba(239, 68, 68, 0.35);
}
.delete-confirm {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  align-items: center;
}
.warn {
  margin: 0;
  flex: 1 1 100%;
  color: #fecaca;
  font-weight: 650;
}
.ghost,
.secondary,
.primary,
.danger {
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
  padding: 0.4rem 0.65rem;
}
.primary {
  border: none;
  background: var(--success-strong);
  color: #fff;
  padding: 0.45rem 0.65rem;
  margin-bottom: 0.5rem;
  font-weight: 650;
}
.danger {
  border: none;
  background: var(--danger);
  color: #fff;
  padding: 0.45rem 0.65rem;
  font-weight: 650;
}
</style>
