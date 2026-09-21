<script setup lang="ts">
import { computed } from "vue";

import { closeMapsChooser, mapsChooserAddress, mapsChooserAppsForTarget, mapsChooserTarget } from "../mapsChooser";

const apps = computed(() => {
  const target = mapsChooserTarget.value;
  return target ? mapsChooserAppsForTarget(target) : [];
});

const heading = computed(() => (mapsChooserTarget.value?.kind === "coords" ? "Открыть координаты" : "Открыть адрес"));
const hint = computed(() =>
  mapsChooserTarget.value?.kind === "coords"
    ? "Выберите приложение карт, чтобы открыть точку с координатами из Wialon."
    : "На iPhone нет системного списка карт, как на Android — выберите приложение здесь."
);
</script>

<template>
  <div v-if="mapsChooserAddress" class="overlay" @click.self="closeMapsChooser()">
    <article class="sheet" role="dialog" aria-modal="true" aria-label="Открыть в картах">
      <h2>{{ heading }}</h2>
      <p class="addr">{{ mapsChooserAddress }}</p>
      <p class="hint">{{ hint }}</p>
      <a
        v-for="app in apps"
        :key="app.id"
        class="app-btn"
        :href="app.href"
        target="_blank"
        rel="noopener noreferrer"
        @click="closeMapsChooser()"
      >
        {{ app.label }}
      </a>
      <button type="button" class="ghost" @click="closeMapsChooser()">Отмена</button>
    </article>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 140;
  background: rgba(2, 6, 23, 0.72);
  backdrop-filter: blur(8px);
  display: grid;
  align-items: end;
  justify-items: center;
  padding: 0.75rem 0.75rem calc(0.75rem + env(safe-area-inset-bottom, 0));
}
.sheet {
  width: min(440px, 100%);
  border-radius: 18px 18px 14px 14px;
  border: 1px solid var(--border);
  background: var(--bg-elevated);
  padding: 1rem 1rem 0.85rem;
  display: grid;
  gap: 0.4rem;
}
h2 {
  margin: 0;
  font-size: 1.02rem;
}
.addr {
  margin: 0;
  color: #e2e8f0;
  font-size: 0.9rem;
  line-height: 1.35;
  word-break: break-word;
}
.hint {
  margin: 0 0 0.25rem;
  color: var(--text-muted);
  font-size: 0.78rem;
  line-height: 1.35;
}
.app-btn,
.ghost {
  width: 100%;
  min-height: 44px;
  border-radius: 12px;
  font-weight: 650;
  display: grid;
  place-items: center;
  text-decoration: none;
}
.app-btn {
  border: 1px solid var(--border-strong);
  background: var(--surface);
  color: #fff;
}
.ghost {
  border: none;
  background: transparent;
  color: #94a3b8;
}
</style>
