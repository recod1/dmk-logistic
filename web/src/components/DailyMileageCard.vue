<script setup lang="ts">
import { computed, reactive, watch } from "vue";

import { DAILY_MILEAGE_STATUS_LABEL, formatOdometer } from "../dailyMileage";
import type { DailyMileageDay } from "../types";

const props = defineProps<{
  days: DailyMileageDay[];
  editable: boolean;
  busy?: boolean;
}>();

const emit = defineEmits<{
  save: [payload: { day_msk: string; odometer_start: number; odometer_end: number; km: number }];
}>();

type Draft = { start: string; end: string; km: string; kmTouched: boolean };

const drafts = reactive<Record<string, Draft>>({});

function toInput(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "";
  return formatOdometer(value);
}

function parseNumber(raw: string): number | null {
  const text = raw.trim().replace(",", ".");
  if (!text) return null;
  const value = Number(text);
  return Number.isFinite(value) ? value : null;
}

const daysStamp = computed(() =>
  props.days
    .map(
      (day) =>
        `${day.day_msk}|${day.status}|${day.odometer_start}|${day.odometer_end}|${day.km}|${day.confirmed_at}|${day.pending_sync ? "1" : "0"}`
    )
    .join(";")
);

watch(
  daysStamp,
  () => {
    for (const day of props.days) {
      drafts[day.day_msk] = {
        start: toInput(day.odometer_start),
        end: toInput(day.odometer_end),
        km: day.km == null ? "" : String(day.km),
        kmTouched: false
      };
    }
  },
  { immediate: true }
);

function draftOf(day: DailyMileageDay): Draft {
  return (
    drafts[day.day_msk] || {
      start: toInput(day.odometer_start),
      end: toInput(day.odometer_end),
      km: day.km == null ? "" : String(day.km),
      kmTouched: false
    }
  );
}

function syncKm(dayMsk: string): void {
  const draft = drafts[dayMsk];
  if (!draft || draft.kmTouched) return;
  const start = parseNumber(draft.start);
  const end = parseNumber(draft.end);
  draft.km = start != null && end != null && end >= start ? String(Math.round(end - start)) : "";
}

function onKmTouched(dayMsk: string): void {
  const draft = drafts[dayMsk];
  if (draft) draft.kmTouched = true;
}

function suggestedLine(day: DailyMileageDay): string {
  return `${formatOdometer(day.suggested_odometer_start)} → ${formatOdometer(day.suggested_odometer_end)} · ${
    day.suggested_km == null ? "—" : `${day.suggested_km} км`
  }`;
}

function parsed(day: DailyMileageDay): { start: number; end: number; km: number } | null {
  const draft = draftOf(day);
  const start = parseNumber(draft.start);
  const end = parseNumber(draft.end);
  const km = parseNumber(draft.km);
  if (start == null || end == null || km == null) return null;
  if (start < 0 || end < start || km < 0) return null;
  return { start, end, km: Math.round(km) };
}

function isDirty(day: DailyMileageDay): boolean {
  const values = parsed(day);
  if (!values) return true;
  return (
    formatOdometer(values.start) !== formatOdometer(day.odometer_start) ||
    formatOdometer(values.end) !== formatOdometer(day.odometer_end) ||
    values.km !== day.km
  );
}

function isCorrectionDraft(day: DailyMileageDay): boolean {
  const values = parsed(day);
  if (!values) return false;
  return (
    formatOdometer(values.start) !== formatOdometer(day.suggested_odometer_start) ||
    formatOdometer(values.end) !== formatOdometer(day.suggested_odometer_end) ||
    values.km !== day.suggested_km
  );
}

function canSave(day: DailyMileageDay): boolean {
  return Boolean(parsed(day)) && (day.status === "pending" || isDirty(day));
}

function buttonLabel(day: DailyMileageDay): string {
  if (isCorrectionDraft(day)) return "Сохранить правку";
  if (day.status === "pending" || isDirty(day)) return "Подтвердить";
  return "Подтверждено";
}

function statusClass(status: DailyMileageDay["status"]): string {
  if (status === "corrected") return "status-chip warn";
  if (status === "confirmed") return "status-chip ok";
  return "status-chip";
}

const hasDays = computed(() => props.days.length > 0);

function onSave(day: DailyMileageDay): void {
  const values = parsed(day);
  if (!values || props.busy) return;
  emit("save", {
    day_msk: day.day_msk,
    odometer_start: values.start,
    odometer_end: values.end,
    km: values.km
  });
}
</script>

<template>
  <section v-if="hasDays" class="daily-mileage">
    <h3>Сверка пробега за сутки</h3>
    <p class="hint">Сутки по московскому времени. Одометр на начало и конец суток и пробег за день.</p>
    <article v-for="day in days" :key="day.day_msk" class="day-card">
      <div class="day-head">
        <strong>{{ day.day_label }}</strong>
        <span :class="statusClass(day.status)">{{ DAILY_MILEAGE_STATUS_LABEL[day.status] }}</span>
      </div>
      <p v-if="day.pending_sync" class="hint">Сохранено на телефоне, отправится при появлении сети.</p>
      <p class="suggested">По данным рейса: {{ suggestedLine(day) }}</p>
      <template v-if="editable && drafts[day.day_msk]">
        <label>
          Одометр на начало суток
          <input
            v-model="drafts[day.day_msk].start"
            type="text"
            inputmode="decimal"
            :disabled="busy"
            @input="syncKm(day.day_msk)"
          />
        </label>
        <label>
          Одометр на конец суток
          <input
            v-model="drafts[day.day_msk].end"
            type="text"
            inputmode="decimal"
            :disabled="busy"
            @input="syncKm(day.day_msk)"
          />
        </label>
        <label>
          Пробег за сутки, км
          <input
            v-model="drafts[day.day_msk].km"
            type="text"
            inputmode="numeric"
            :disabled="busy"
            @input="onKmTouched(day.day_msk)"
          />
        </label>
        <button
          class="primary"
          type="button"
          :disabled="busy || !canSave(day)"
          @click="onSave(day)"
        >
          {{ buttonLabel(day) }}
        </button>
      </template>
      <template v-else>
        <div class="kv">
          <span class="k">Одометр на начало суток</span>
          <span class="v">{{ formatOdometer(day.odometer_start) }}</span>
        </div>
        <div class="kv">
          <span class="k">Одометр на конец суток</span>
          <span class="v">{{ formatOdometer(day.odometer_end) }}</span>
        </div>
        <div class="kv">
          <span class="k">Пробег за сутки</span>
          <span class="v">{{ day.km == null ? "—" : `${day.km} км` }}</span>
        </div>
        <p v-if="day.status === 'corrected'" class="warn-text">
          Водитель изменил данные относительно показаний рейса.
        </p>
      </template>
    </article>
  </section>
</template>

<style scoped>
.daily-mileage {
  display: grid;
  gap: 0.55rem;
  margin-top: 0.35rem;
  padding-top: 0.45rem;
  border-top: 1px solid #243043;
}
.daily-mileage h3 {
  margin: 0;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-label, #94a3b8);
}
.hint,
.suggested,
.warn-text {
  margin: 0;
  font-size: 0.8rem;
  color: var(--text-muted, #94a3b8);
}
.warn-text {
  color: #fbbf24;
}
.day-card {
  display: grid;
  gap: 0.4rem;
  padding: 0.55rem 0.15rem 0.15rem;
}
.day-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
.status-chip {
  border: 1px solid #334155;
  border-radius: 999px;
  padding: 0.1rem 0.5rem;
  font-size: 0.75rem;
  color: #c7d2fe;
}
.status-chip.ok {
  border-color: #166534;
  color: #86efac;
}
.status-chip.warn {
  border-color: #854d0e;
  color: #fde68a;
}
label {
  display: grid;
  gap: 0.2rem;
  font-size: 0.78rem;
  color: var(--text-label, #94a3b8);
}
input {
  min-height: 40px;
  border-radius: 10px;
  border: 1px solid #334155;
  background: #0b1220;
  color: #fff;
  padding: 0.45rem 0.62rem;
  font: inherit;
}
.primary {
  border: none;
  border-radius: 12px;
  background: linear-gradient(180deg, #3b82f6, #2563eb);
  color: #fff;
  padding: 0.55rem 0.78rem;
  font-weight: 650;
  min-height: 42px;
}
.primary:disabled {
  opacity: 0.55;
}
.kv {
  display: grid;
  grid-template-columns: minmax(8rem, 42%) 1fr;
  gap: 0.4rem;
  align-items: baseline;
}
.k {
  color: var(--text-label, #94a3b8);
  font-size: 0.8rem;
}
.v {
  color: var(--text-body, #e2e8f0);
}
</style>
