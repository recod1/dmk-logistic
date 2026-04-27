<script setup lang="ts">
import { ref } from "vue";

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

function statusLabel(s: string): string {
  const t = (s || "").trim();
  if (t === "confirmed") return "Подтверждено";
  if (t === "commented") return "С комментарием";
  return "Ожидает подтверждения";
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
      <p class="meta">{{ record.date_salary }} · {{ statusLabel(record.status_driver) }}</p>
      <p class="sum">Итого: {{ record.total.toFixed(2) }} ₽</p>
      <dl class="grid">
        <dt>г/мг/рд/пр</dt>
        <dd>{{ record.type_route }}</dd>
        <dt>Оклад / суточные</dt>
        <dd>{{ record.sum_status }} / {{ record.sum_daily }}</dd>
        <dt>Загр 2р / шаттл / загр-выгр</dt>
        <dd>{{ record.load_2_trips }} / {{ record.calc_shuttle }} / {{ record.sum_load_unload }}</dd>
        <dt>Штора / возврат / доп.шаттл / доп.точка / АЗС</dt>
        <dd>{{ record.sum_curtain }} / {{ record.sum_return }} / {{ record.sum_add_shuttle }} / {{ record.sum_add_point }} / {{ record.sum_gas_station }}</dd>
        <dt>Паллеты гипер/метро/ашан</dt>
        <dd>{{ record.pallets_hyper }} / {{ record.pallets_metro }} / {{ record.pallets_ashan }}</dd>
        <dt>Тарифы км 3/3.5/5/10/12/12.5</dt>
        <dd>{{ record.rate_3km }} / {{ record.rate_3_5km }} / {{ record.rate_5km }} / {{ record.rate_10km }} / {{ record.rate_12km }} / {{ record.rate_12_5km }}</dd>
        <dt>Пробег / комп.связи / стаж / 10%</dt>
        <dd>{{ record.mileage }} / {{ record.sum_cell_compensation }} / {{ record.experience }} / {{ record.percent_10 }}</dd>
        <dt>Премия / удержать / возмещение / ДР</dt>
        <dd>{{ record.sum_bonus }} / {{ record.withhold }} / {{ record.compensation }} / {{ record.dr }}</dd>
        <dt>Без сут/ДР/прем/стажа · в день</dt>
        <dd>{{ record.sum_without_daily_dr_bonus_exp }} · {{ record.sum_without_daily_dr_bonus }}</dd>
        <dt>Адреса</dt>
        <dd>{{ record.load_address }} → {{ record.unload_address }}</dd>
        <dt>ТС / прицеп / № рейса</dt>
        <dd>{{ record.transport }} / {{ record.trailer_number }} / {{ record.route_number }}</dd>
      </dl>
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
  grid-template-columns: 1fr 1.2fr;
  gap: 0.35rem 0.65rem;
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
