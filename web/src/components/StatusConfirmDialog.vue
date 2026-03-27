<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  open: boolean;
  nextStatusLabel: string;
  datetimeLocal: string;
}>();

const emit = defineEmits<{
  cancel: [];
  confirm: [datetimeLocal: string];
  "update:datetimeLocal": [value: string];
}>();

const localValue = computed({
  get: () => props.datetimeLocal,
  set: (v: string) => emit("update:datetimeLocal", v)
});
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
      <div class="actions">
        <button type="button" class="secondary" @click="emit('cancel')">Отмена</button>
        <button type="button" class="primary" @click="emit('confirm', localValue)">Подтвердить</button>
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
input[type="datetime-local"] {
  border-radius: 10px;
  border: 1px solid #334155;
  background: #111827;
  color: #f8fafc;
  padding: 0.55rem 0.65rem;
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
