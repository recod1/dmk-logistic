<script setup lang="ts">
import { openMapsChooser } from "../mapsChooser";

defineProps<{
  address: string;
}>();
</script>

<template>
  <button type="button" class="maps-link" @click.stop="openMapsChooser(address)">{{ address }}</button>
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
</style>
