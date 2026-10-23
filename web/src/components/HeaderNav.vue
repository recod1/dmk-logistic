<script setup lang="ts">
import type { BottomNavId, BottomNavItem } from "./BottomNav.vue";
import NavIcon from "./NavIcon.vue";

defineProps<{
  items: BottomNavItem[];
  activeId: BottomNavId | null;
  iconsOnly?: boolean;
  chatsUnread?: boolean;
  routesUnread?: boolean;
  salaryUnread?: boolean;
}>();

const emit = defineEmits<{
  select: [item: BottomNavItem];
}>();
</script>

<template>
  <nav v-if="items.length" class="header-nav" :class="{ 'icons-only': iconsOnly }" aria-label="Разделы">
    <button
      v-for="item in items"
      :key="item.id"
      type="button"
      class="tab"
      :class="{ active: item.id === activeId }"
      :title="item.label"
      :aria-label="item.label"
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
    gap: 0.2rem;
    min-width: 0;
    overflow: hidden;
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
  border: 1px solid #4b6280;
  border-radius: 12px;
  background: #1e2a3d;
  color: #e2e8f0;
  font: inherit;
}
.tab.active {
  color: #fff;
  background: #1d4ed8;
  border-color: #93c5fd;
}
.label {
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.01em;
  line-height: 1;
  white-space: nowrap;
}
.icons-only .label {
  display: none;
}
.icons-only .tab {
  width: 42px;
  padding: 0;
  justify-content: center;
}
</style>
