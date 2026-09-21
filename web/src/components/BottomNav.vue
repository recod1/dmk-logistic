<script setup lang="ts">
import NavIcon from "./NavIcon.vue";

export type BottomNavId = "home" | "routes" | "chats" | "salary" | "users" | "settings";

export interface BottomNavItem {
  id: BottomNavId;
  label: string;
  section: string;
}

defineProps<{
  items: BottomNavItem[];
  activeId: BottomNavId | null;
  chatsUnread?: boolean;
  routesUnread?: boolean;
}>();

const emit = defineEmits<{
  select: [item: BottomNavItem];
}>();
</script>

<template>
  <nav class="bottom-nav" aria-label="Разделы">
    <button
      v-for="item in items"
      :key="item.id"
      type="button"
      class="tab"
      :class="{ active: item.id === activeId }"
      @click="emit('select', item)"
    >
      <NavIcon
        :name="item.id"
        :unread="(item.id === 'chats' && chatsUnread) || (item.id === 'routes' && routesUnread)"
      />
      <span class="label">{{ item.label }}</span>
    </button>
  </nav>
</template>

<style scoped>
.bottom-nav {
  display: none;
}
@media (max-width: 760px) {
  .bottom-nav {
    position: relative;
    z-index: 20;
    flex: 0 0 auto;
    flex-shrink: 0;
    align-self: stretch;
    display: grid;
    grid-auto-flow: column;
    grid-auto-columns: 1fr;
    align-items: center;
    gap: 0.1rem;
    box-sizing: border-box;
    height: auto;
    max-height: calc(4.25rem + env(safe-area-inset-bottom, 0px));
    overflow: hidden;
    padding: 0.22rem 0.35rem calc(0.22rem + env(safe-area-inset-bottom, 0px));
    background: #030712;
    border-top: 1px solid var(--border);
  }
}
.tab {
  display: grid;
  justify-items: center;
  align-content: center;
  gap: 0.12rem;
  height: 48px;
  min-height: 48px;
  max-height: 48px;
  padding: 0.15rem 0.1rem;
  border: none;
  border-radius: 12px;
  background: transparent;
  color: #94a3b8;
}
.tab.active {
  color: #93c5fd;
  background: rgba(37, 99, 235, 0.16);
}
.label {
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.01em;
  line-height: 1;
}
</style>
