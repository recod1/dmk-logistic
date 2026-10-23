<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { fromDatetimeLocalToIso } from "../datetimeLocal";
import { datetimeLocalKey } from "../factTime";
import { etaIsLate, lastLateReasonText, registrationIsLate } from "../lateArrival";

const props = defineProps<{
  open: boolean;
  nextStatusLabel: string;
  datetimeLocal: string;
  initialDatetimeLocal?: string;
  pressedAtIso?: string;
  showOdometer?: boolean;
  odometer?: string;
  odometerPrefillSource?: "wialon" | null;
  initialOdometer?: string;
  telemetryLoading?: boolean;
  showEta?: boolean;
  etaTime?: string;
  allowSkip?: boolean;
  lateKind?: "" | "process" | "registration";
  datePoint?: string;
  pointTime?: string;
  existingLateReason?: string;
}>();

const emit = defineEmits<{
  cancel: [];
  confirm: [
    payload: {
      datetimeLocal: string;
      odometer: string;
      odometer_source: "manual" | "wialon" | null;
      etaTime: string;
      skipped?: boolean;
      lateReason?: string;
    }
  ];
  "update:datetimeLocal": [value: string];
  "update:odometer": [value: string];
  "update:etaTime": [value: string];
}>();

const odometerMode = ref<"ask" | "edit" | "manual">("manual");
const lateReason = ref("");

const localValue = computed({
  get: () => props.datetimeLocal,
  set: (v: string) => emit("update:datetimeLocal", v)
});

const odometerValue = computed({
  get: () => props.odometer ?? "",
  set: (v: string) => emit("update:odometer", v)
});

const etaValue = computed({
  get: () => props.etaTime ?? "",
  set: (v: string) => emit("update:etaTime", v)
});

watch(
  () => props.open,
  (open) => {
    if (open) {
      lateReason.value = "";
    }
  }
);

watch(
  () => [props.open, props.odometerPrefillSource, props.initialOdometer, props.telemetryLoading] as const,
  () => {
    if (!props.open) {
      odometerMode.value = "manual";
      return;
    }
    if (props.telemetryLoading) {
      return;
    }
    if (props.odometerPrefillSource === "wialon" && (props.initialOdometer || "").trim()) {
      const typed = (odometerValue.value || "").trim();
      const prefill = (props.initialOdometer || "").trim();
      odometerMode.value = typed && typed !== prefill ? "edit" : "ask";
      return;
    }
    odometerMode.value = "manual";
  }
);

const odometerReady = computed(() => {
  if (!props.showOdometer || props.allowSkip) {
    return true;
  }
  return Boolean((odometerValue.value || "").trim());
});

const etaReady = computed(() => {
  if (!props.showEta || props.allowSkip) {
    return true;
  }
  return Boolean((etaValue.value || "").trim());
});

const occurredIso = computed(() => {
  const current = localValue.value;
  const initial = props.initialDatetimeLocal || current;
  if (datetimeLocalKey(initial) === datetimeLocalKey(current) && props.pressedAtIso) {
    return props.pressedAtIso;
  }
  try {
    return fromDatetimeLocalToIso(current);
  } catch {
    return props.pressedAtIso || "";
  }
});

const reusedLateReason = computed(() => lastLateReasonText(props.existingLateReason));

const isLateNow = computed(() => {
  if (props.allowSkip || !props.lateKind) {
    return false;
  }
  if (props.lateKind === "process") {
    return etaIsLate(props.datePoint, props.pointTime, etaValue.value);
  }
  if (props.lateKind === "registration") {
    return registrationIsLate(occurredIso.value, props.datePoint, props.pointTime);
  }
  return false;
});

const needsLateReason = computed(() => isLateNow.value && !reusedLateReason.value);

const formReady = computed(() => odometerReady.value && etaReady.value);

function acceptWialon(): void {
  odometerMode.value = "ask";
  confirm();
}

function editWialon(): void {
  odometerMode.value = "edit";
}

function confirm(): void {
  if (!formReady.value) {
    return;
  }
  const odo = (props.showOdometer ? (odometerValue.value || "").trim() : "").trim();
  const initial = (props.initialOdometer || "").trim();
  let source: "manual" | "wialon" | null = null;
  if (props.showOdometer) {
    if (odo && props.odometerPrefillSource === "wialon" && odo === initial && odometerMode.value !== "edit") {
      source = "wialon";
    } else if (odo) {
      source = "manual";
    }
  }
  emit("confirm", {
    datetimeLocal: localValue.value,
    odometer: odo,
    odometer_source: source,
    etaTime: (etaValue.value || "").trim(),
    skipped: false,
    lateReason: lateReason.value.trim() || reusedLateReason.value
  });
}

function skip(): void {
  emit("confirm", {
    datetimeLocal: localValue.value,
    odometer: "",
    odometer_source: null,
    etaTime: "",
    skipped: true
  });
}
</script>

<template>
  <div v-if="open" class="overlay" @click.self="emit('cancel')">
    <article class="dialog" role="dialog" aria-modal="true">
      <h2 class="title">Подтвердите этап</h2>
      <p class="desc">
        Следующий этап: <strong>{{ nextStatusLabel }}</strong>.
        <template v-if="allowSkip"> Сверьте дату, время и одометр — или пропустите.</template>
        <template v-else> Проверьте время и показания одометра.</template>
      </p>
      <label class="field">
        Дата и время
        <input v-model="localValue" type="datetime-local" step="60" />
      </label>
      <label v-if="showEta" class="field">
        Ориентировочное время прибытия
        <input v-model="etaValue" type="time" step="60" lang="ru" />
      </label>
      <div v-if="showOdometer" class="odo-block">
        <p class="field-label">Одометр</p>
        <p v-if="telemetryLoading" class="hint">Запрашиваем Wialon… Можно ввести вручную, не дожидаясь ответа.</p>
        <template v-if="!telemetryLoading && odometerMode === 'ask'">
          <p class="wialon-value">{{ odometerValue || "—" }}</p>
          <p class="hint">Данные подтянуты из Wialon. Они верны или их нужно исправить?</p>
          <div class="ask-actions">
            <button type="button" class="primary" :disabled="!formReady" @click="acceptWialon">Верны</button>
            <button type="button" class="secondary" @click="editWialon">Исправить</button>
          </div>
        </template>
        <label v-else class="field nested">
          <input v-model="odometerValue" inputmode="text" placeholder="Например: 123456 или 123456 км" />
          <small v-if="odometerPrefillSource === 'wialon'" class="hint">Исправьте значение из Wialon и сохраните.</small>
          <small v-else-if="allowSkip" class="hint">Можно оставить пустым и пропустить.</small>
          <small v-else class="hint">Если Wialon не ответил — введите показания вручную.</small>
        </label>
      </div>
      <label v-if="needsLateReason" class="field">
        Причина опоздания
        <textarea v-model="lateReason" rows="3" maxlength="1000" placeholder="Например: пробка на МКАД" />
        <small class="hint">Если есть причина — укажите. Этап сохранится в любом случае.</small>
      </label>
      <div class="actions">
        <button type="button" class="secondary" @click="emit('cancel')">Отмена</button>
        <button v-if="allowSkip" type="button" class="ghost" @click="skip">Пропустить</button>
        <button v-if="odometerMode !== 'ask'" type="button" class="primary" :disabled="!formReady" @click="confirm">
          Сохранить
        </button>
      </div>
    </article>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  width: 100%;
  height: 100%;
  background: rgba(2, 6, 23, 0.72);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: max(1rem, env(safe-area-inset-top, 0px)) 1rem max(1rem, env(safe-area-inset-bottom, 0px));
  box-sizing: border-box;
  overflow: auto;
  -webkit-overflow-scrolling: touch;
}
:global(html.keyboard-open) .overlay {
  height: var(--vv-height, 100%);
  transform: translate3d(0, var(--vv-offset, 0px), 0);
}
.dialog {
  width: min(420px, 100%);
  max-width: 100%;
  margin: auto 0;
  border-radius: 18px;
  border: 1px solid var(--border);
  background: var(--bg-elevated);
  padding: 1.15rem;
  box-shadow: var(--shadow);
  animation: dialog-in 0.2s ease;
}
.title {
  margin: 0 0 0.5rem;
  font-size: 1.08rem;
}
.desc {
  margin: 0 0 0.75rem;
  color: var(--text-muted);
  font-size: 0.92rem;
  line-height: 1.45;
}
.field {
  display: grid;
  gap: 0.35rem;
  margin-bottom: 1rem;
  font-size: 0.88rem;
  color: #cbd5e1;
}
.field.nested {
  margin-bottom: 0;
}
.field-label {
  margin: 0 0 0.35rem;
  font-size: 0.88rem;
  color: #cbd5e1;
}
.odo-block {
  margin-bottom: 1rem;
}
.wialon-value {
  margin: 0 0 0.4rem;
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text-heading);
}
.ask-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.55rem;
}
textarea {
  border-radius: 12px;
  border: 1px solid var(--border-strong);
  background: var(--surface);
  color: var(--text);
  padding: 0.6rem 0.7rem;
  font: inherit;
  font-size: 16px;
  width: 100%;
  resize: vertical;
}
input[type="datetime-local"],
input[type="time"],
input {
  border-radius: 12px;
  border: 1px solid var(--border-strong);
  background: var(--surface);
  color: var(--text);
  padding: 0.6rem 0.7rem;
  font-size: 16px;
  width: 100%;
  max-width: 100%;
  min-width: 0;
}
.hint {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.8rem;
  line-height: 1.35;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: flex-end;
}
.primary,
.secondary,
.ghost {
  min-height: 42px;
  border-radius: 12px;
  padding: 0.5rem 0.9rem;
  font-weight: 650;
}
.primary {
  border: 1px solid #93c5fd;
  background: #2563eb;
  color: #fff;
}
.primary:disabled {
  opacity: 0.48;
}
.secondary {
  border: 1px solid #60a5fa;
  background: #1e3a5f;
  color: #e0f2fe;
}
.ghost {
  border: 1px solid #6b7c93;
  background: #243044;
  color: #f1f5f9;
}
</style>
