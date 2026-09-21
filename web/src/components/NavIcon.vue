<script setup lang="ts">
import type { BottomNavId } from "./BottomNav.vue";

defineProps<{
  name: BottomNavId;
  unread?: boolean;
}>();
</script>

<template>
  <span class="icon-wrap">
    <svg v-if="name === 'home'" viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M4.5 10.5 12 4l7.5 6.5V20a1.5 1.5 0 0 1-1.5 1.5h-4.2v-6.2h-3.6V21.5H6A1.5 1.5 0 0 1 4.5 20Z"
        fill="none"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linejoin="round"
      />
    </svg>
    <svg v-else-if="name === 'routes'" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 9.2h10.2V16H3z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" />
      <path d="M13.2 11.2h3.8L20 14.4V16h-6.8z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" />
      <circle cx="6.6" cy="16.7" r="1.7" fill="none" stroke="currentColor" stroke-width="1.8" />
      <circle cx="16.6" cy="16.7" r="1.7" fill="none" stroke="currentColor" stroke-width="1.8" />
      <path d="M3 12.2h10.2" fill="none" stroke="currentColor" stroke-width="1.8" />
    </svg>
    <svg v-else-if="name === 'chats'" viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M5 18.5 6.2 15A7.5 7.5 0 1 1 12 19.5H7.2Z"
        fill="none"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linejoin="round"
      />
    </svg>
    <svg v-else-if="name === 'users'" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="9" cy="8" r="3.1" fill="none" stroke="currentColor" stroke-width="1.8" />
      <path d="M4.2 18.6c.5-3 2.5-4.6 4.8-4.6s4.3 1.6 4.8 4.6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
      <circle cx="16.6" cy="8.6" r="2.4" fill="none" stroke="currentColor" stroke-width="1.8" />
      <path d="M15.2 14.2c1.9.2 3.5 1.5 4.1 3.8" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
    </svg>
    <svg v-else-if="name === 'settings'" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="1.8" />
      <path
        d="M19.4 13a7.8 7.8 0 0 0 .1-2l2-1.5-2-3.4-2.3.5a7.6 7.6 0 0 0-1.7-1L15 3.2h-4l-.5 2.4a7.6 7.6 0 0 0-1.7 1l-2.3-.5-2 3.4 2 1.5a7.8 7.8 0 0 0 .1 2l-2 1.5 2 3.4 2.3-.5a7.6 7.6 0 0 0 1.7 1l.5 2.4h4l.5-2.4a7.6 7.6 0 0 0 1.7-1l2.3.5 2-3.4Z"
        fill="none"
        stroke="currentColor"
        stroke-width="1.6"
        stroke-linejoin="round"
      />
    </svg>
    <svg v-else viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3.5" y="6.5" width="17" height="11" rx="2.2" fill="none" stroke="currentColor" stroke-width="1.8" />
      <path d="M3.5 10.5h17" fill="none" stroke="currentColor" stroke-width="1.8" />
      <path d="M8 14.2h3.2" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
    </svg>
    <span v-if="unread" class="unread" />
  </span>
</template>

<style scoped>
.icon-wrap {
  position: relative;
  width: 22px;
  height: 22px;
  flex-shrink: 0;
}
.icon-wrap svg {
  width: 22px;
  height: 22px;
  display: block;
}
.unread {
  position: absolute;
  top: -2px;
  right: -3px;
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: var(--success);
  box-shadow: 0 0 0 2px rgba(3, 7, 18, 0.94);
  animation: nav-unread-pulse 1.8s ease-in-out infinite;
}
@keyframes nav-unread-pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.18);
    opacity: 0.72;
  }
}
</style>
