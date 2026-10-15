<script setup lang="ts">
import { computed } from "vue";

import { formatFactPressedCaption, timeSourceCaption } from "../factTime";

const props = defineProps<{
  time?: string | null;
  source?: string | null;
  pressedAt?: string | null;
}>();

const sourceCaption = computed(() => timeSourceCaption(props.source));
const pressedCaption = computed(() => formatFactPressedCaption(props.time, props.pressedAt));
</script>

<template>
  <span class="fact-time">
    <span>{{ time || "—" }}</span>
    <span v-if="sourceCaption" class="fact-src">{{ sourceCaption }}</span>
    <span v-if="pressedCaption" class="fact-src">{{ pressedCaption }}</span>
  </span>
</template>

<style scoped>
.fact-time {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.28rem 0.4rem;
}
.fact-src {
  color: #94a3b8;
  font-size: 0.72rem;
  font-weight: 650;
  letter-spacing: 0.01em;
  padding: 0.04rem 0.38rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.14);
  white-space: nowrap;
}
</style>
