<script setup lang="ts">
import { computed, ref, watch } from "vue";

const props = defineProps<{
  open: boolean;
  uploading: boolean;
}>();

const emit = defineEmits<{
  cancel: [];
  confirm: [files: File[]];
}>();

const inputRef = ref<HTMLInputElement | null>(null);
const picked = ref<File[]>([]);

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      picked.value = [];
    }
  }
);

const canSubmit = computed(() => picked.value.length > 0 && !props.uploading);

function onFileChange(ev: Event): void {
  const input = ev.target as HTMLInputElement;
  const list = input.files ? Array.from(input.files) : [];
  picked.value = list;
}

function triggerPick(): void {
  inputRef.value?.click();
}

function submit(): void {
  if (!canSubmit.value) {
    return;
  }
  emit("confirm", picked.value);
}
</script>

<template>
  <div v-if="open" class="overlay" @click.self="emit('cancel')">
    <article class="dialog" role="dialog" aria-modal="true">
      <h2 class="title">Фото документов</h2>
      <p class="desc">
        Для этапа «Забрал документы» выберите снимки из галереи (можно несколько). Без фото переход не будет отправлен на
        сервер; в офлайне файлы сохранятся и отправятся при появлении сети.
      </p>
      <input
        ref="inputRef"
        type="file"
        accept="image/*"
        multiple
        class="hidden-input"
        @change="onFileChange"
      />
      <button type="button" class="secondary pick" :disabled="uploading" @click="triggerPick">
        {{ picked.length ? `Выбрано файлов: ${picked.length}` : "Выбрать из галереи" }}
      </button>
      <ul v-if="picked.length" class="names">
        <li v-for="(f, i) in picked" :key="`${i}-${f.name}`">{{ f.name }}</li>
      </ul>
      <div class="actions">
        <button type="button" class="secondary ghost" :disabled="uploading" @click="emit('cancel')">Отмена</button>
        <button type="button" class="primary" :disabled="!canSubmit" @click="submit">
          {{ uploading ? "Отправка…" : "Подтвердить" }}
        </button>
      </div>
    </article>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 110;
  background: rgba(2, 6, 23, 0.72);
  display: grid;
  place-items: center;
  padding: 1rem;
}
.dialog {
  width: min(440px, 100%);
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
.hidden-input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}
.pick {
  width: 100%;
  margin-bottom: 0.5rem;
}
.names {
  margin: 0 0 0.75rem;
  padding-left: 1.1rem;
  color: #cbd5e1;
  font-size: 0.85rem;
  max-height: 6rem;
  overflow: auto;
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
.ghost {
  background: transparent;
}
</style>
