<script setup lang="ts">
import { connectionHint, connectionLabel, connectionTone } from "../connectionWatch";

defineProps<{
  alertCount?: number;
}>();

const emit = defineEmits<{
  open: [];
}>();
</script>

<template>
  <button
    type="button"
    class="conn-pill"
    :class="connectionTone"
    :title="connectionHint"
    :aria-label="`Связь: ${connectionLabel}`"
    @click="emit('open')"
  >
    <span class="dot" aria-hidden="true" />
    <span class="txt">{{ connectionLabel }}</span>
    <span v-if="alertCount" class="err">{{ alertCount > 9 ? "9+" : alertCount }}</span>
  </button>
</template>

<style scoped>
.conn-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.32rem;
  max-width: 100%;
  min-height: 22px;
  padding: 0.08rem 0.42rem 0.08rem 0.32rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: rgba(15, 23, 42, 0.72);
  color: var(--text-muted);
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.01em;
  line-height: 1;
}
.dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #64748b;
  flex: 0 0 auto;
}
.txt {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.err {
  min-width: 1.05rem;
  padding: 0.05rem 0.22rem;
  border-radius: 999px;
  background: #7f1d1d;
  color: #fecaca;
  font-size: 0.62rem;
  text-align: center;
}
.ok {
  border-color: rgba(34, 197, 94, 0.28);
  color: #86efac;
}
.ok .dot {
  background: #22c55e;
}
.warn {
  border-color: rgba(245, 158, 11, 0.35);
  color: #fcd34d;
}
.warn .dot {
  background: #f59e0b;
}
.bad {
  border-color: rgba(239, 68, 68, 0.4);
  color: #fca5a5;
}
.bad .dot {
  background: #ef4444;
}
</style>
