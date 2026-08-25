<script setup lang="ts">
import { computed, ref } from "vue";

import type { SalaryRecord } from "../api";

const props = defineProps<{
  record: SalaryRecord;
  isDriver: boolean;
  busy: boolean;
}>();

const emit = defineEmits<{
  back: [];
  confirm: [];
  comment: [text: string];
  openChat: [];
}>();

const commentText = ref("");

type DetailRow = { label: string; value: string };

function statusLabel(s: string): string {
  const t = (s || "").trim();
  if (t === "confirmed") return "Подтверждено";
  if (t === "commented") return "С комментарием";
  return "Ожидает подтверждения";
}

function isNonZeroNumber(v: number): boolean {
  return typeof v === "number" && Number.isFinite(v) && v !== 0;
}

function isNonEmptyText(v: string | null | undefined): boolean {
  const t = (v || "").trim();
  return Boolean(t) && t !== "0";
}

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
</script>

<template>
  <section class="wrap">
    <header class="head">
      <button type="button" class="ghost" @click="emit('back')">← Назад</button>
      <h1>Расчёт #{{ record.id }}</h1>
      <button type="button" class="secondary" @click="emit('openChat')">Чат расчёта</button>
    </header>
    <div class="card">
      <p class="meta">{{ record.date_salary }} · {{ statusLabel(record.status_driver) }}</p>
      <p class="sum">Итого: {{ record.total.toFixed(2) }} ₽</p>
      <dl v-if="detailRows.length" class="grid">
        <template v-for="row in detailRows" :key="row.label">
          <dt>{{ row.label }}</dt>
          <dd>{{ row.value }}</dd>
        </template>
      </dl>
      <p v-else class="empty">Все значения равны нулю</p>
      <p v-if="record.comment_driver && record.comment_driver.trim()" class="comment">
        Комментарий водителя: {{ record.comment_driver }}
      </p>
    </div>
    <div v-if="isDriver" class="card">
      <h2>Действия водителя</h2>
      <button type="button" class="primary" :disabled="busy || record.status_driver === 'confirmed'" @click="emit('confirm')">Подтвердить расчёт</button>
      <label class="field">
        Комментарий бухгалтеру
        <textarea v-model="commentText" rows="3" placeholder="Текст комментария" />
      </label>
      <button type="button" class="secondary" :disabled="busy || !commentText.trim()" @click="emit('comment', commentText.trim())">
        Отправить комментарий
      </button>
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
  border: 1px solid #243043;
  border-radius: 14px;
  padding: 0.85rem;
  background: rgba(15, 23, 42, 0.6);
}
.meta {
  color: #94a3b8;
  margin: 0 0 0.35rem;
}
.sum {
  font-size: 1.15rem;
  font-weight: 700;
  margin: 0 0 0.65rem;
  color: #fde68a;
}
.grid {
  display: grid;
  grid-template-columns: minmax(8rem, 1fr) 1.2fr;
  gap: 0.4rem 0.65rem;
  font-size: 0.85rem;
  margin: 0;
}
dt {
  color: #94a3b8;
}
dd {
  margin: 0;
  word-break: break-word;
}
.empty {
  margin: 0;
  color: #94a3b8;
  font-size: 0.88rem;
}
.comment {
  margin-top: 0.65rem;
  color: #fca5a5;
  font-size: 0.9rem;
}
.field {
  display: grid;
  gap: 0.25rem;
  margin: 0.65rem 0 0.35rem;
  font-size: 0.88rem;
}
textarea {
  border-radius: 8px;
  border: 1px solid #334155;
  background: #0b1220;
  color: #fff;
  padding: 0.45rem;
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
  padding: 0.4rem 0.65rem;
}
.primary {
  border: none;
  border-radius: 8px;
  background: #16a34a;
  color: #fff;
  padding: 0.45rem 0.65rem;
  margin-bottom: 0.5rem;
}
</style>
