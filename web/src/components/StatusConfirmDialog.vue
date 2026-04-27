<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  open: boolean;
  nextStatusLabel: string;
  datetimeLocal: string;
  showOdometer?: boolean;
  odometer?: string;
  odometerPrefillSource?: "wialon" | null;
  initialOdometer?: string;
}>();

const emit = defineEmits<{
  cancel: [];
  confirm: [payload: { datetimeLocal: string; odometer: string; odometer_source: "manual" | "wialon" | null }];
  "update:datetimeLocal": [value: string];
  "update:odometer": [value: string];
}>();

const localValue = computed({
  get: () => props.datetimeLocal,
  set: (v: string) => emit("update:datetimeLocal", v)
});

const odometerValue = computed({
  get: () => props.odometer ?? "",
  set: (v: string) => emit("update:odometer", v)
});

function confirm(): void {
  const odo = (props.showOdometer ? (odometerValue.value || "").trim() : "").trim();
  const initial = (props.initialOdometer || "").trim();
  let source: "manual" | "wialon" | null = null;
  if (props.showOdometer) {
    if (odo && props.odometerPrefillSource === "wialon" && odo === initial) {
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
      <h2 class="title">Подтвердите время</h2>
      <p class="desc">
        Следующий этап: <strong>{{ nextStatusLabel }}</strong>. Проверьте дату и время события (время устройства). При
        необходимости скорректируйте вручную.
      </p>
      <label class="field">
        Дата и время
        <input v-model="localValue" type="datetime-local" step="60" />
      </label>
      <label v-if="showOdometer" class="field">
        Одометр
        <input v-model="odometerValue" inputmode="text" placeholder="Например: 123456 или 123456 км" />
        <small v-if="odometerPrefillSource === 'wialon'" class="hint">Подставлено из Wialon — можно подтвердить или исправить.</small>
        <small v-else class="hint">Если связи с Wialon нет — введите вручную.</small>
      </label>
      <div class="actions">
        <button type="button" class="secondary" @click="emit('cancel')">Отмена</button>
        <button type="button" class="primary" @click="confirm">Подтвердить</button>
      </div>
    </article>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(2, 6, 23, 0.72);
  display: grid;
  place-items: center;
  padding: 1rem;
}
.dialog {
  width: min(420px, 100%);
  border-radius: 16px;
  border: 1px solid #334155;
  background: #0b1220;
  padding: 1.1rem;
  box-shadow: 0 20px 50px rgba(2, 6, 23, 0.55);
}
.title {
  margin: 0 0 0.5rem;
  font-size: 1.05rem;
}
.desc {
  margin: 0 0 0.75rem;
  color: #94a3b8;
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
input[type="datetime-local"],
input {
  border-radius: 10px;
  border: 1px solid #334155;
  background: #111827;
  color: #f8fafc;
  padding: 0.55rem 0.65rem;
}
.hint {
  color: #94a3b8;
  font-size: 0.8rem;
  line-height: 1.35;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: flex-end;
}
.primary {
  border: none;
  border-radius: 10px;
  background: #2563eb;
  color: #fff;
  padding: 0.5rem 0.85rem;
}
.secondary {
  border: 1px solid #334155;
  border-radius: 10px;
  background: transparent;
  color: #e2e8f0;
  padding: 0.5rem 0.85rem;
}
</style>
