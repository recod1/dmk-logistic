<script setup lang="ts">
import { computed, ref, watch } from "vue";

const props = defineProps<{
  open: boolean;
  nextStatusLabel: string;
  datetimeLocal: string;
  showOdometer?: boolean;
  odometer?: string;
  odometerPrefillSource?: "wialon" | null;
  initialOdometer?: string;
  telemetryLoading?: boolean;
}>();

const emit = defineEmits<{
  cancel: [];
  confirm: [payload: { datetimeLocal: string; odometer: string; odometer_source: "manual" | "wialon" | null }];
  "update:datetimeLocal": [value: string];
  "update:odometer": [value: string];
}>();

const odometerMode = ref<"ask" | "edit" | "manual">("manual");

const localValue = computed({
  get: () => props.datetimeLocal,
  set: (v: string) => emit("update:datetimeLocal", v)
});

const odometerValue = computed({
  get: () => props.odometer ?? "",
  set: (v: string) => emit("update:odometer", v)
});

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
      odometerMode.value = "ask";
      return;
    }
    odometerMode.value = "manual";
  }
);

const odometerReady = computed(() => {
  if (!props.showOdometer) {
    return true;
  }
  if (props.telemetryLoading) {
    return false;
  }
  return Boolean((odometerValue.value || "").trim());
});

function acceptWialon(): void {
  odometerMode.value = "ask";
  confirm();
}

function editWialon(): void {
  odometerMode.value = "edit";
}

function confirm(): void {
  if (!odometerReady.value) {
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
  emit("confirm", { datetimeLocal: localValue.value, odometer: odo, odometer_source: source });
}
</script>

<template>
  <div v-if="open" class="overlay" @click.self="emit('cancel')">
    <article class="dialog" role="dialog" aria-modal="true">
      <h2 class="title">Подтвердите этап</h2>
      <p class="desc">
        Следующий этап: <strong>{{ nextStatusLabel }}</strong>. Проверьте время и показания одометра.
      </p>
      <label class="field">
        Дата и время
        <input v-model="localValue" type="datetime-local" step="60" />
      </label>
      <div v-if="showOdometer" class="odo-block">
        <p class="field-label">Одометр</p>
        <p v-if="telemetryLoading" class="hint">Запрашиваем показания из Wialon…</p>
        <template v-else-if="odometerMode === 'ask'">
          <p class="wialon-value">{{ odometerValue || "—" }}</p>
          <p class="hint">Данные подтянуты из Wialon. Они верны или их нужно исправить?</p>
          <div class="ask-actions">
            <button type="button" class="primary" @click="acceptWialon">Верны</button>
            <button type="button" class="secondary" @click="editWialon">Исправить</button>
          </div>
        </template>
        <label v-else class="field nested">
          <input v-model="odometerValue" inputmode="text" placeholder="Например: 123456 или 123456 км" />
          <small v-if="odometerPrefillSource === 'wialon'" class="hint">Исправьте значение из Wialon и сохраните.</small>
          <small v-else class="hint">Если Wialon не ответил — введите показания вручную.</small>
        </label>
      </div>
      <div class="actions">
        <button type="button" class="secondary" @click="emit('cancel')">Отмена</button>
        <button v-if="odometerMode !== 'ask'" type="button" class="primary" :disabled="!odometerReady" @click="confirm">
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
input[type="datetime-local"],
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
.secondary {
  min-height: 42px;
  border-radius: 12px;
  padding: 0.5rem 0.9rem;
  font-weight: 650;
}
.primary {
  border: none;
  background: linear-gradient(180deg, #3b82f6, #2563eb);
  color: #fff;
}
.primary:disabled {
  opacity: 0.48;
}
.secondary {
  border: 1px solid var(--border-strong);
  background: transparent;
  color: #e2e8f0;
}
</style>
