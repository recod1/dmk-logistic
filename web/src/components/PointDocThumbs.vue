<script setup lang="ts">
import { onUnmounted, ref, watch } from "vue";

import { fetchPointDocumentBlob } from "../api";

const props = defineProps<{
  token: string;
  images: Array<{ id: number; content_type: string }>;
}>();

const loaded = ref<Array<{ id: number; url: string; thumb: boolean }>>([]);
const failedIds = ref<number[]>([]);
const loadErrors = ref<Record<number, string>>({});

let seq = 0;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function loadBlobWithRetries(imageId: number, thumbnail: boolean): Promise<Blob> {
  let lastErr: Error | null = null;
  for (let attempt = 0; attempt < 4; attempt += 1) {
    try {
      if (attempt > 0) {
        await sleep(320 * attempt);
      }
      return await fetchPointDocumentBlob(props.token, imageId, { thumbnail });
    } catch (e) {
      lastErr = e instanceof Error ? e : new Error(String(e));
    }
  }
  throw lastErr ?? new Error("load failed");
}

watch(
  [() => props.token, () => props.images],
  async () => {
    const my = ++seq;
    loaded.value.forEach((x) => URL.revokeObjectURL(x.url));
    loaded.value = [];
    failedIds.value = [];
    loadErrors.value = {};
    if (!props.token || !props.images?.length) {
      return;
    }
    const next: Array<{ id: number; url: string; thumb: boolean }> = [];
    const failed: number[] = [];
    const errs: Record<number, string> = {};

    for (const img of props.images) {
      if (my !== seq) {
        return;
      }
      try {
        let blob: Blob;
        try {
          blob = await loadBlobWithRetries(img.id, true);
        } catch {
          blob = await loadBlobWithRetries(img.id, false);
        }
        if (blob.size === 0) {
          blob = await loadBlobWithRetries(img.id, false);
        }
        next.push({ id: img.id, url: URL.createObjectURL(blob), thumb: true });
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        failed.push(img.id);
        errs[img.id] = msg.length > 120 ? `${msg.slice(0, 120)}…` : msg;
      }
    }

    if (my === seq) {
      loaded.value = next;
      failedIds.value = failed;
      loadErrors.value = errs;
    }
  },
  { immediate: true, deep: true }
);

onUnmounted(() => {
  loaded.value.forEach((x) => URL.revokeObjectURL(x.url));
});

async function openPreview(item: { id: number; url: string; thumb: boolean }): Promise<void> {
  try {
    const blob = await loadBlobWithRetries(item.id, false);
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank", "noopener,noreferrer");
    window.setTimeout(() => URL.revokeObjectURL(url), 120_000);
  } catch {
    window.open(item.url, "_blank", "noopener,noreferrer");
  }
}
</script>

<template>
  <div v-if="images?.length" class="docs-block">
    <p class="label">Документы (фото)</p>
    <p v-if="failedIds.length && !loaded.length" class="err">
      Не удалось загрузить превью ({{ failedIds.length }} шт.). Проверьте сессию или доступ к файлам на сервере.
    </p>
    <p v-else-if="failedIds.length" class="warn">
      Часть файлов не загрузилась ({{ failedIds.length }}). Остальные ниже.
    </p>
    <div class="thumbs">
      <button
        v-for="item in loaded"
        :key="item.id"
        type="button"
        class="thumb"
        @click="openPreview(item)"
      >
        <img :src="item.url" alt="Документ" loading="lazy" decoding="async" />
      </button>
      <div v-for="fid in failedIds" :key="'f-' + fid" class="thumb thumb-fail" :title="loadErrors[fid] || 'Ошибка'">
        <span>?</span>
      </div>
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
  margin: 0 0 0.35rem;
  font-size: 0.82rem;
  color: #fca5a5;
}
.warn {
  margin: 0 0 0.35rem;
  font-size: 0.8rem;
  color: #fcd34d;
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
.thumb-fail {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: default;
  color: #94a3b8;
  font-weight: 700;
  font-size: 1.25rem;
}
</style>
