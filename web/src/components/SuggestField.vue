<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";

export type SuggestItem = { id: number; label: string };

const props = defineProps<{
  modelValue: string;
  items: SuggestItem[];
  placeholder?: string;
  picked?: boolean;
  emptyLabel?: string;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: string];
  pick: [item: SuggestItem];
  clear: [];
}>();

const wrap = ref<HTMLElement | null>(null);
const open = ref(false);

const matches = computed(() => {
  const q = (props.modelValue || "").trim().toLowerCase();
  const list = props.items || [];
  if (!q) {
    return list.slice(0, 12);
  }
  return list.filter((item) => item.label.toLowerCase().includes(q)).slice(0, 12);
});

function onPick(item: SuggestItem): void {
  emit("update:modelValue", item.label);
  emit("pick", item);
  open.value = false;
}

function onClear(): void {
  emit("clear");
  open.value = false;
}

function onDocPointerDown(event: PointerEvent): void {
  if (!open.value) {
    return;
  }
  const target = event.target as Node | null;
  if (wrap.value && target && wrap.value.contains(target)) {
    return;
  }
  open.value = false;
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") {
    open.value = false;
  }
}

onMounted(() => {
  document.addEventListener("pointerdown", onDocPointerDown, true);
  document.addEventListener("keydown", onKeydown);
});

onUnmounted(() => {
  document.removeEventListener("pointerdown", onDocPointerDown, true);
  document.removeEventListener("keydown", onKeydown);
});
</script>

<template>
  <div ref="wrap" class="suggest-wrap">
    <span v-if="$slots.label" class="suggest-label"><slot name="label" /></span>
    <input
      :value="modelValue"
      :placeholder="placeholder || 'Начните вводить'"
      autocomplete="off"
      @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
      @focus="open = true"
    />
    <p v-if="picked && modelValue" class="picked">Выбран: {{ modelValue }}</p>
    <div v-if="open && (matches.length || emptyLabel)" class="suggest">
      <button v-if="emptyLabel" type="button" class="suggest-item" @mousedown.prevent="onClear">
        {{ emptyLabel }}
      </button>
      <button
        v-for="item in matches"
        :key="item.id"
        type="button"
        class="suggest-item"
        @mousedown.prevent="onPick(item)"
      >
        {{ item.label }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.suggest-wrap {
  position: relative;
  display: grid;
  gap: 0.26rem;
  min-width: 0;
  width: 100%;
}
.suggest-label {
  min-width: 0;
}
.suggest-wrap input {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  appearance: none;
  -webkit-appearance: none;
  border-radius: 10px;
  border: 1px solid var(--border-strong);
  background: var(--bg-elevated);
  color: var(--text);
  padding: 0.5rem 0.62rem;
  font: inherit;
  font-size: 16px;
  box-shadow: none;
}
.suggest-wrap input::placeholder {
  color: var(--text-faint);
}
.picked {
  margin: 0.15rem 0 0;
  color: var(--text-muted);
  font-size: 0.82rem;
}
.suggest {
  position: absolute;
  z-index: 6;
  left: 0;
  right: 0;
  top: calc(100% + 4px);
  max-height: 220px;
  overflow: auto;
  border: 1px solid var(--border-strong);
  border-radius: 10px;
  background: var(--bg-elevated);
  box-shadow: var(--shadow);
}
.suggest-item {
  width: 100%;
  text-align: left;
  background: transparent;
  border-radius: 0;
  border: none;
  border-bottom: 1px solid var(--border);
  color: var(--text-body);
  padding: 0.45rem 0.65rem;
  font: inherit;
}
.suggest-item:last-child {
  border-bottom: none;
}
.suggest-item:hover,
.suggest-item:focus {
  background: var(--primary-soft);
}
</style>
