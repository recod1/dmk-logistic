<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";

import { fetchShiftImageBlob } from "../api";
import type { DriverShiftDetails } from "../types";

const props = defineProps<{
  shift: DriverShiftDetails | null;
  loading: boolean;
  error: string;
  authToken: string;
}>();

const emit = defineEmits<{
  back: [];
  openRoute: [routeId: string];
}>();

const SLOT_LABELS: Record<string, string> = {
  front: "Спереди",
  rear: "Сзади",
  left: "Слева",
  right: "Справа"
};

const thumbs = ref<Record<number, string>>({});

function kindLabel(kind: string, slot: string): string {
  const side = SLOT_LABELS[slot] || "";
  if (kind === "start_vehicle") {
    return `Начало · транспорт${side ? ` · ${side}` : ""}`;
  }
  if (kind === "end_vehicle") {
    return `Окончание · транспорт${side ? ` · ${side}` : ""}`;
  }
  if (kind === "start_waybill") {
    return "Начало · путевой лист";
  }
  return kind;
}

function revokeThumbs(): void {
  Object.values(thumbs.value).forEach((url) => URL.revokeObjectURL(url));
  thumbs.value = {};
}

watch(
  () => [props.shift?.id, props.authToken, props.shift?.images?.length] as const,
  async () => {
    revokeThumbs();
    const shift = props.shift;
    if (!shift || !props.authToken) {
      return;
    }
    const next: Record<number, string> = {};
    for (const img of shift.images) {
      try {
        const blob = await fetchShiftImageBlob(props.authToken, img.id, { thumbnail: true });
        next[img.id] = URL.createObjectURL(blob);
      } catch {
        // skip broken file
      }
    }
    thumbs.value = next;
  },
  { immediate: true }
);

onUnmounted(() => {
  revokeThumbs();
});

const title = computed(() => props.shift?.title || "Вахта");
</script>

<template>
  <section class="wrap">
    <button class="ghost" type="button" @click="emit('back')">← Назад</button>
    <article v-if="shift" class="card">
      <h2>{{ title }}</h2>
      <p class="meta">{{ shift.status === "active" ? "Действует" : "Закончена" }} · {{ shift.driver_full_name }}</p>
      <h3>Фото</h3>
      <div class="photos">
        <div v-for="img in shift.images" :key="img.id" class="photo">
          <img v-if="thumbs[img.id]" :src="thumbs[img.id]" :alt="kindLabel(img.kind, img.slot)" />
          <small>{{ kindLabel(img.kind, img.slot) }}</small>
        </div>
        <p v-if="!shift.images.length" class="empty">Нет фото</p>
      </div>
      <h3>Рейсы за вахту</h3>
      <div class="routes">
        <button
          v-for="route in shift.routes"
          :key="route.id"
          class="route-card"
          type="button"
          @click="emit('openRoute', route.id)"
        >
          <strong>#{{ route.id }}</strong>
          <small>ТС: {{ route.number_auto || "—" }} · точек: {{ route.points_count }}</small>
        </button>
        <p v-if="!shift.routes.length" class="empty">За эту вахту рейсов нет</p>
      </div>
    </article>
    <p v-else-if="loading">Загрузка…</p>
    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>

<style scoped>
.wrap {
  display: grid;
  gap: 0.85rem;
  width: 100%;
  max-width: 720px;
  margin: 0 auto;
}
.card {
  display: grid;
  gap: 0.7rem;
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: rgba(17, 24, 39, 0.88);
}
h2,
h3 {
  margin: 0;
}
.meta {
  margin: 0;
  color: var(--text-muted);
}
.photos,
.routes {
  display: grid;
  gap: 0.55rem;
}
.photos {
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
}
.photo {
  display: grid;
  gap: 0.28rem;
}
.photo img {
  width: 100%;
  height: 110px;
  object-fit: cover;
  border-radius: 10px;
  border: 1px solid var(--border);
}
.route-card {
  text-align: left;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface-2, #111827);
  color: #fff;
  padding: 0.7rem;
  display: grid;
  gap: 0.2rem;
}
.empty,
.error {
  margin: 0;
}
.error {
  color: #fca5a5;
}
.ghost {
  width: auto;
  justify-self: start;
  background: transparent;
  color: #bfdbfe;
  border: 1px solid var(--border-strong);
  border-radius: 10px;
  padding: 0.4rem 0.7rem;
}
</style>
