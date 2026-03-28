<script setup lang="ts">
import { onUnmounted, ref, watch } from "vue";

import { fetchPointDocumentBlob } from "../api";

const props = defineProps<{
  token: string;
  images: Array<{ id: number; content_type: string }>;
}>();

const loaded = ref<Array<{ id: number; url: string }>>([]);
const error = ref(false);

let seq = 0;

watch(
  [() => props.token, () => props.images],
  async () => {
    const my = ++seq;
    loaded.value.forEach((x) => URL.revokeObjectURL(x.url));
    loaded.value = [];
    error.value = false;
    if (!props.token || !props.images?.length) {
      return;
    }
    const next: Array<{ id: number; url: string }> = [];
    for (const img of props.images) {
      if (my !== seq) {
        return;
      }
      try {
        const blob = await fetchPointDocumentBlob(props.token, img.id);
        next.push({ id: img.id, url: URL.createObjectURL(blob) });
      } catch {
        error.value = true;
      }
    }
    if (my === seq) {
      loaded.value = next;
    }
  },
  { immediate: true, deep: true }
);

onUnmounted(() => {
  loaded.value.forEach((x) => URL.revokeObjectURL(x.url));
});

function open(url: string): void {
  window.open(url, "_blank", "noopener,noreferrer");
}
</script>

<template>
  <div v-if="images?.length" class="docs-block">
    <p class="label">Документы (фото)</p>
    <p v-if="error && !loaded.length" class="err">Не удалось загрузить превью</p>
    <div class="thumbs">
      <button
        v-for="item in loaded"
        :key="item.id"
        type="button"
        class="thumb"
        @click="open(item.url)"
      >
        <img :src="item.url" alt="Документ" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.docs-block {
  margin-top: 0.35rem;
}
.label {
  margin: 0 0 0.35rem;
  font-size: 0.82rem;
  color: #94a3b8;
}
.err {
  margin: 0;
  font-size: 0.82rem;
  color: #fca5a5;
}
.thumbs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}
.thumb {
  padding: 0;
  border: 1px solid #334155;
  border-radius: 8px;
  overflow: hidden;
  width: 72px;
  height: 72px;
  background: #0f172a;
  cursor: pointer;
}
.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
</style>
