<script setup lang="ts">
import { computed, ref, watch } from "vue";

const props = defineProps<{
  open: boolean;
}>();

const emit = defineEmits<{
  cancel: [];
  confirm: [reason: string];
}>();

const reason = ref("");

watch(
  () => props.open,
  (open) => {
    if (open) {
      reason.value = "";
    }
  }
);

const canSubmit = computed(() => reason.value.trim().length > 0);

function submit(): void {
  if (!canSubmit.value) {
    return;
  }
  emit("confirm", reason.value.trim());
}
</script>

<template>
  <div v-if="open" class="overlay" @click.self="emit('cancel')">
    <article class="dialog" role="dialog" aria-modal="true">
      <h2>Причина опоздания</h2>
      <p class="desc">Укажите, почему прибытие позже плана. Поле обязательно.</p>
      <textarea v-model="reason" rows="4" maxlength="1000" placeholder="Например: пробка на МКАД" />
      <div class="actions">
        <button class="primary" type="button" :disabled="!canSubmit" @click="submit">Сохранить</button>
        <button class="ghost" type="button" @click="emit('cancel')">Отмена</button>
      </div>
    </article>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 80;
  background: rgba(2, 6, 23, 0.72);
  display: grid;
  place-items: center;
  padding: 1rem;
}
.dialog {
  width: min(420px, 100%);
  display: grid;
  gap: 0.7rem;
  padding: 1.05rem;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: #0f172a;
  box-shadow: var(--shadow);
}
h2 {
  margin: 0;
  font-size: 1.05rem;
}
.desc {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.88rem;
}
textarea {
  width: 100%;
  border-radius: 12px;
  border: 1px solid #334155;
  background: #0b1220;
  color: #fff;
  padding: 0.65rem 0.75rem;
  resize: vertical;
  font: inherit;
}
.actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}
.primary {
  background: var(--primary-strong);
  color: #fff;
  border: none;
  border-radius: 10px;
  padding: 0.5rem 0.85rem;
}
.primary:disabled {
  opacity: 0.45;
}
.ghost {
  background: transparent;
  color: #bfdbfe;
  border: 1px solid var(--border-strong);
  border-radius: 10px;
  padding: 0.5rem 0.85rem;
}
</style>
