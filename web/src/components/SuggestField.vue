<script setup lang="ts">
import { computed, ref } from "vue";

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
</script>

<template>
  <label class="suggest-wrap">
    <slot name="label" />
    <input
      :value="modelValue"
      :placeholder="placeholder || 'Начните вводить'"
      autocomplete="off"
      @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
      @focus="open = true"
      @blur="window.setTimeout(() => (open = false), 180)"
    />
    <p v-if="picked && modelValue" class="picked">Выбран: {{ modelValue }}</p>
    <div v-if="open && (matches.length || emptyLabel)" class="suggest">
      <button v-if="emptyLabel" type="button" class="suggest-item" @mousedown.prevent="emit('clear')">
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
  </label>
</template>

<style scoped>
.suggest-wrap {
  position: relative;
  display: grid;
  gap: 0.28rem;
}
.picked {
  margin: 0.15rem 0 0;
  color: #86efac;
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
  border: 1px solid #334155;
  border-radius: 10px;
  background: #0b1220;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.35);
}
.suggest-item {
  width: 100%;
  text-align: left;
  background: transparent;
  border-radius: 0;
  border-bottom: 1px solid #1e293b;
  color: #e2e8f0;
  padding: 0.45rem 0.65rem;
}
.suggest-item:last-child {
  border-bottom: none;
}
.suggest-item:hover,
.suggest-item:focus {
  background: rgba(37, 99, 235, 0.2);
}
</style>
