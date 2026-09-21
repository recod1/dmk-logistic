<script setup lang="ts">
import { computed } from "vue";

import { openMapsChooserCoords } from "../mapsChooser";

const props = defineProps<{
  lat?: number | null;
  lng?: number | null;
}>();

const hasCoords = computed(
  () => typeof props.lat === "number" && Number.isFinite(props.lat) && typeof props.lng === "number" && Number.isFinite(props.lng)
);

const label = computed(() => {
  if (!hasCoords.value) {
    return "—";
  }
  return `${Number(props.lat).toFixed(6)}, ${Number(props.lng).toFixed(6)}`;
});

function open(): void {
  if (!hasCoords.value) {
    return;
  }
  openMapsChooserCoords(Number(props.lat), Number(props.lng));
}
</script>

<template>
  <button v-if="hasCoords" type="button" class="maps-link" @click.stop="open">{{ label }}</button>
  <span v-else class="empty">—</span>
</template>

<style scoped>
.maps-link {
  display: inline;
  padding: 0;
  margin: 0;
  border: none;
  background: none;
  color: #93c5fd;
  text-decoration: underline;
  text-underline-offset: 0.15em;
  font: inherit;
  text-align: left;
  cursor: pointer;
  word-break: break-word;
}
.empty {
  color: inherit;
}
</style>
