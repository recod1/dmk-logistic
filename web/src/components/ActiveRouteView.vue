<script setup lang="ts">
import PointList from "./PointList.vue";
import type { RouteDto } from "../types";

defineProps<{
  route: RouteDto;
  syncing: boolean;
  syncMessage: string;
}>();

const emit = defineEmits<{
  accept: [];
  advanceStatus: [pointId: number];
  manualSync: [];
}>();
</script>

<template>
  <section class="stack">
    <article class="route-card">
      <div class="row">
        <h1>Активный рейс #{{ route.id }}</h1>
        <span class="chip">{{ route.status }}</span>
      </div>
      <p><strong>ТС:</strong> {{ route.number_auto || "—" }}</p>
      <p><strong>Прицеп:</strong> {{ route.trailer_number || "—" }}</p>
      <p><strong>Темп.:</strong> {{ route.temperature || "—" }}</p>
      <p><strong>Диспетчер:</strong> {{ route.dispatcher_contacts || "—" }}</p>
      <button v-if="route.status === 'new'" @click="emit('accept')">Принять рейс</button>
    </article>

    <article class="route-card">
      <div class="row">
        <h2>Синхронизация</h2>
        <button :disabled="syncing" @click="emit('manualSync')">{{ syncing ? "..." : "Sync" }}</button>
      </div>
      <p>{{ syncMessage }}</p>
    </article>

    <PointList :points="route.points" :syncing="syncing" @advance-status="emit('advanceStatus', $event)" />
  </section>
</template>

<style scoped>
.stack {
  display: grid;
  gap: 0.75rem;
}
.route-card {
  background: #111827;
  border: 1px solid #374151;
  border-radius: 12px;
  padding: 0.9rem;
}
.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}
h1,
h2,
p {
  margin: 0 0 0.35rem;
}
.chip {
  border-radius: 999px;
  background: #1f2937;
  padding: 0.15rem 0.6rem;
}
button {
  border: none;
  border-radius: 10px;
  background: #3b82f6;
  color: #fff;
  padding: 0.45rem 0.75rem;
}
</style>

