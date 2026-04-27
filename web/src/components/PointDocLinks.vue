<script setup lang="ts">
import { ref } from "vue";

import { fetchPointDocumentBlob } from "../api";

const props = defineProps<{
  token: string;
  images: Array<{ id: number; content_type: string }>;
}>();

const openingId = ref<number | null>(null);
const errors = ref<Record<number, string>>({});

async function openDocument(imageId: number): Promise<void> {
  const nextErr = { ...errors.value };
  delete nextErr[imageId];
  errors.value = nextErr;
  openingId.value = imageId;
  try {
    const blob = await fetchPointDocumentBlob(props.token, imageId, { thumbnail: false });
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank", "noopener,noreferrer");
    window.setTimeout(() => URL.revokeObjectURL(url), 120_000);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    errors.value = { ...errors.value, [imageId]: msg.length > 200 ? `${msg.slice(0, 200)}…` : msg };
  } finally {
    openingId.value = null;
  }
}
</script>

<template>
  <div v-if="images?.length" class="docs-block">
    <p class="label">Вложения ({{ images.length }}) — открыть по клику</p>
    <ul class="doc-list">
      <li v-for="(img, idx) in images" :key="img.id" class="doc-row">
        <button type="button" class="open-btn" :disabled="openingId === img.id" @click="openDocument(img.id)">
          {{ openingId === img.id ? "Загрузка…" : `Файл ${idx + 1}` }}
        </button>
        <span class="meta">{{ img.content_type }}</span>
        <span v-if="errors[img.id]" class="err">{{ errors[img.id] }}</span>
      </li>
    </ul>
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
.doc-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.doc-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.82rem;
}
.open-btn {
  border: 1px solid #334155;
  border-radius: 8px;
  background: #1e293b;
  color: #e2e8f0;
  padding: 0.25rem 0.55rem;
  cursor: pointer;
  font-size: 0.82rem;
}
.open-btn:disabled {
  opacity: 0.65;
  cursor: wait;
}
.meta {
  color: #64748b;
  font-size: 0.78rem;
}
.err {
  color: #fca5a5;
  flex-basis: 100%;
  font-size: 0.78rem;
}
</style>
