<script setup lang="ts">
import type { BottomNavId, BottomNavItem } from "./BottomNav.vue";
import NavIcon from "./NavIcon.vue";

defineProps<{
  items: BottomNavItem[];
  activeId: BottomNavId | null;
  chatsUnread?: boolean;
  routesUnread?: boolean;
  salaryUnread?: boolean;
}>();

const emit = defineEmits<{
  select: [item: BottomNavItem];
}>();
</script>

<template>
  <nav v-if="items.length" class="header-nav" aria-label="Разделы">
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
        :unread="(item.id === 'chats' && chatsUnread) || (item.id === 'routes' && routesUnread) || (item.id === 'salary' && salaryUnread)"
      />
      <span class="label">{{ item.label }}</span>
    </button>
  </nav>
</template>

<style scoped>
.header-nav {
  display: none;
}
@media (min-width: 761px) {
  .header-nav {
    display: flex;
    align-items: center;
    flex-wrap: nowrap;
    justify-content: flex-end;
    gap: 0.12rem;
    min-width: 0;
    overflow: visible;
    flex-wrap: nowrap;
  }
}
.tab {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  min-height: 42px;
  flex: 0 0 auto;
  white-space: nowrap;
  padding: 0.28rem 0.55rem;
  border: 1px solid transparent;
  border-radius: 12px;
  background: transparent;
  color: #94a3b8;
  font: inherit;
}
.tab.active {
  color: #93c5fd;
  background: rgba(37, 99, 235, 0.16);
  border-color: rgba(96, 165, 250, 0.28);
}
.label {
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.01em;
  line-height: 1;
  white-space: nowrap;
}
@media (min-width: 761px) and (max-width: 1280px) {
  .header-nav {
    flex-wrap: wrap;
    max-width: min(640px, 62vw);
  }
  .label {
    font-size: 0.72rem;
  }
  .tab {
    padding: 0.22rem 0.38rem;
    gap: 0.22rem;
  }
}
</style>
