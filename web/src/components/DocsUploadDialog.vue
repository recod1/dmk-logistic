<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";

const props = defineProps<{
  open: boolean;
  uploading: boolean;
}>();

const emit = defineEmits<{
  cancel: [];
  confirm: [files: File[]];
}>();

const galleryInputRef = ref<HTMLInputElement | null>(null);
const cameraInputRef = ref<HTMLInputElement | null>(null);
const picked = ref<File[]>([]);
const lastPreviewUrl = ref("");

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      picked.value = [];
    }
  }
);

watch(
  picked,
  (files) => {
    if (lastPreviewUrl.value) {
      URL.revokeObjectURL(lastPreviewUrl.value);
      lastPreviewUrl.value = "";
    }
    const last = files[files.length - 1];
    lastPreviewUrl.value = last ? URL.createObjectURL(last) : "";
  },
  { deep: true }
);

onUnmounted(() => {
  if (lastPreviewUrl.value) {
    URL.revokeObjectURL(lastPreviewUrl.value);
  }
});

const canSubmit = computed(() => picked.value.length > 0 && !props.uploading);
const hasPhotos = computed(() => picked.value.length > 0);

function onFileChange(ev: Event): void {
  const input = ev.target as HTMLInputElement;
  const list = input.files ? Array.from(input.files) : [];
  if (list.length) {
    picked.value = [...picked.value, ...list];
  }
  input.value = "";
}

function removePicked(index: number): void {
  picked.value.splice(index, 1);
}

function triggerPick(): void {
  galleryInputRef.value?.click();
}

function triggerCamera(): void {
  cameraInputRef.value?.click();
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
      <p v-if="!hasPhotos" class="desc">
        Сделайте фото камерой. После снимка спросим, нужно ли ещё одно, или можно отправлять.
      </p>
      <p v-else class="desc">
        Сейчас {{ picked.length }} фото. Сделайте ещё снимок или отправьте, если хватит.
      </p>
      <input
        ref="galleryInputRef"
        type="file"
        accept="image/*"
        multiple
        class="hidden-input"
        @change="onFileChange"
      />
      <input
        ref="cameraInputRef"
        type="file"
        accept="image/*"
        capture="environment"
        class="hidden-input"
        @change="onFileChange"
      />

      <template v-if="!hasPhotos">
        <button type="button" class="primary pick" :disabled="uploading" @click="triggerCamera">Сделать фото</button>
        <button type="button" class="secondary pick" :disabled="uploading" @click="triggerPick">Выбрать из галереи</button>
        <div class="actions">
          <button type="button" class="secondary ghost" @click="emit('cancel')">Отмена</button>
        </div>
      </template>

      <template v-else>
        <img v-if="lastPreviewUrl" class="preview" :src="lastPreviewUrl" alt="Последнее фото" />
        <ul class="names">
          <li v-for="(f, i) in picked" :key="`${i}-${f.name}-${f.size}-${f.lastModified}`">
            <span>{{ f.name || `Фото ${i + 1}` }}</span>
            <button type="button" class="remove" :disabled="uploading" @click="removePicked(i)">Убрать</button>
          </li>
        </ul>
        <div class="ask">
          <button type="button" class="more pick" :disabled="uploading" @click="triggerCamera">Сделать ещё фото</button>
          <button type="button" class="primary pick" :disabled="!canSubmit" @click="submit">
            {{ uploading ? "Сохранение…" : "Хватит, отправить" }}
          </button>
          <button type="button" class="ghost-link" :disabled="uploading" @click="triggerPick">Добавить из галереи</button>
        </div>
        <div class="actions">
          <button type="button" class="secondary ghost" @click="emit('cancel')">Отмена</button>
        </div>
      </template>
    </article>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 110;
  width: 100%;
  max-width: 100vw;
  height: 100%;
  background: rgba(2, 6, 23, 0.72);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: max(1rem, env(safe-area-inset-top, 0px)) 1rem max(1rem, env(safe-area-inset-bottom, 0px));
  box-sizing: border-box;
  overflow: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
}
:global(html.keyboard-open) .overlay {
  height: var(--vv-height, 100%);
  transform: translate3d(0, var(--vv-offset, 0px), 0);
}
.dialog {
  width: min(440px, calc(100vw - 2rem));
  max-width: 100%;
  min-width: 0;
  margin: auto 0;
  border-radius: 18px;
  border: 1px solid var(--border);
  background: var(--bg-elevated);
  padding: 1.15rem;
  box-shadow: var(--shadow);
  animation: dialog-in 0.2s ease;
  box-sizing: border-box;
  overflow-x: hidden;
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
.hidden-input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}
.pick {
  width: 100%;
  max-width: 100%;
  margin-bottom: 0.45rem;
  min-height: 48px;
  box-sizing: border-box;
}
.preview {
  display: block;
  width: 100%;
  max-width: 100%;
  height: auto;
  max-height: min(220px, 40vh);
  object-fit: contain;
  border-radius: 12px;
  border: 1px solid var(--border);
  margin-bottom: 0.55rem;
  background: #0b1220;
}
.ask {
  display: grid;
  gap: 0.4rem;
  margin-bottom: 0.35rem;
}
.ghost-link {
  border: none;
  background: transparent;
  color: #93c5fd;
  min-height: 36px;
  font-size: 0.88rem;
}
.names {
  margin: 0 0 0.75rem;
  padding: 0;
  list-style: none;
  color: #cbd5e1;
  font-size: 0.85rem;
  max-height: 8rem;
  overflow: auto;
  display: grid;
  gap: 0.35rem;
}
.names li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.28rem 0.4rem;
  border: 1px solid var(--border);
  border-radius: 10px;
  min-width: 0;
}
.names li span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.remove {
  border: none;
  background: transparent;
  color: #fca5a5;
  font-size: 0.8rem;
  padding: 0.15rem 0.3rem;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: flex-end;
}
.primary,
.secondary {
  border-radius: 12px;
  padding: 0.5rem 0.9rem;
  font-weight: 650;
  min-height: 42px;
}
.primary {
  border: none;
  background: linear-gradient(180deg, #3b82f6, #2563eb);
  color: #fff;
}
.more {
  border: none;
  background: linear-gradient(180deg, #22c55e, #16a34a);
  color: #fff;
  font-weight: 650;
}
.secondary {
  border: 1px solid var(--border-strong);
  background: transparent;
  color: #e2e8f0;
}
.ghost {
  background: transparent;
}
</style>
