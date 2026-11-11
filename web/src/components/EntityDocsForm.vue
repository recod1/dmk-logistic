<script setup lang="ts">
import { computed } from "vue";

import {
  ENTITY_DOC_SPECS,
  entityDocStatus,
  normalizeEntityDocs,
  type EntityDocsMap,
  type EntityKind,
  type EntityDocValue
} from "../entityDocs";
import { KIND_META, type DocHas } from "../shiftInspection";

const props = defineProps<{
  kind: EntityKind;
  modelValue?: EntityDocsMap | null;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: EntityDocsMap];
}>();

const docs = computed(() => normalizeEntityDocs(props.modelValue, props.kind));
const specs = computed(() => ENTITY_DOC_SPECS[props.kind]);

function patch(key: string, next: Partial<EntityDocValue>): void {
  if (props.disabled) return;
  emit("update:modelValue", {
    ...docs.value,
    [key]: { ...docs.value[key], ...next }
  });
}

function setHas(key: string, value: DocHas): void {
  const current = docs.value[key]?.has;
  patch(key, { has: current === value ? null : value });
}
</script>

<template>
  <div class="docs">
    <article v-for="spec in specs" :key="spec.key" class="doc">
      <div class="head">
        <strong>{{ spec.name }}</strong>
        <span v-if="entityDocStatus(spec, docs[spec.key])" class="pill" :class="entityDocStatus(spec, docs[spec.key])?.c">
          {{ entityDocStatus(spec, docs[spec.key])?.t }}
        </span>
      </div>
      <div class="seg">
        <button type="button" class="y" :class="{ on: docs[spec.key].has === 'y' }" :disabled="disabled" @click="setHas(spec.key, 'y')">Есть</button>
        <button type="button" class="n" :class="{ on: docs[spec.key].has === 'n' }" :disabled="disabled" @click="setHas(spec.key, 'n')">Нет</button>
        <button type="button" class="x" :class="{ on: docs[spec.key].has === 'x' }" :disabled="disabled" @click="setHas(spec.key, 'x')">Не нужен</button>
      </div>
      <template v-if="docs[spec.key].has === 'y'">
        <label v-if="spec.kind && KIND_META[spec.kind]" class="f">
          <span>{{ KIND_META[spec.kind].l1 }}</span>
          <input :value="docs[spec.key].d1" type="date" :disabled="disabled" @change="patch(spec.key, { d1: ($event.target as HTMLInputElement).value })" />
        </label>
        <label v-if="spec.kind && KIND_META[spec.kind]" class="f">
          <span>{{ KIND_META[spec.kind].l2 }}</span>
          <input :value="docs[spec.key].d2" type="date" :disabled="disabled" @change="patch(spec.key, { d2: ($event.target as HTMLInputElement).value })" />
        </label>
        <label v-else-if="spec.needs_exp" class="f">
          <span>Действует до</span>
          <input :value="docs[spec.key].exp" type="date" :disabled="disabled" @change="patch(spec.key, { exp: ($event.target as HTMLInputElement).value })" />
        </label>
      </template>
    </article>
  </div>
</template>

<style scoped>
.docs { display: grid; gap: 10px; }
.doc { border: 1px solid var(--border); border-radius: 12px; padding: 12px; background: var(--surface, rgba(15, 23, 42, 0.55)); }
.head { display: flex; justify-content: space-between; gap: 8px; align-items: flex-start; }
.seg { display: grid; grid-template-columns: repeat(3, 1fr); border: 1.5px solid var(--border); border-radius: 12px; overflow: hidden; margin-top: 8px; }
.seg button { border: 0; background: transparent; min-height: 40px; color: inherit; }
.seg button + button { border-left: 1.5px solid var(--border); }
.seg button.on.y { background: rgba(34, 197, 94, 0.16); color: #4ade80; font-weight: 700; }
.seg button.on.n { background: rgba(239, 68, 68, 0.16); color: #f87171; font-weight: 700; }
.seg button.on.x { background: rgba(59, 130, 246, 0.18); color: #93c5fd; font-weight: 700; }
.f { display: block; margin-top: 8px; }
.f span { display: block; font-size: 0.82rem; color: var(--text-muted); margin-bottom: 4px; }
input { width: 100%; min-height: 42px; border: 1.5px solid var(--border); border-radius: 10px; background: var(--bg-elevated, #0f172a); color: inherit; padding: 8px 10px; }
.pill { display: inline-block; font-size: 0.75rem; font-weight: 600; padding: 2px 8px; border-radius: 999px; }
.pill.ok { background: rgba(34, 197, 94, 0.16); color: #4ade80; }
.pill.warn { background: rgba(245, 158, 11, 0.16); color: #fbbf24; }
.pill.bad { background: rgba(239, 68, 68, 0.16); color: #f87171; }
</style>
