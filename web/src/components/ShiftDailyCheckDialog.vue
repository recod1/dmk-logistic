<script setup lang="ts">
import { computed, ref, watch } from "vue";

import {
  dailyDateLabel,
  hydrateDailyItems,
  type DailyCheckItem,
  type ShiftDailyCheck
} from "../shiftDaily";

const props = defineProps<{
  open: boolean;
  check: ShiftDailyCheck | null;
  busy?: boolean;
  error?: string;
}>();

const emit = defineEmits<{
  cancel: [];
  complete: [items: DailyCheckItem[]];
  skip: [];
}>();

const items = ref<DailyCheckItem[]>([]);
const confirmSkip = ref(false);

watch(
  () => `${props.open}:${props.check?.id ?? ""}`,
  () => {
    items.value = hydrateDailyItems(props.check?.items);
    confirmSkip.value = false;
  },
  { immediate: true }
);

const filled = computed(() => items.value.every((item) => item.st === "ok" || item.st === "bad"));
const titleDate = computed(() => dailyDateLabel(props.check?.check_date));

function setCheck(item: DailyCheckItem, value: "ok" | "bad"): void {
  item.st = item.st === value ? null : value;
  if (item.st !== "bad") {
    item.note = "";
  }
}

function submit(): void {
  if (!filled.value || props.busy) return;
  emit(
    "complete",
    items.value.map((item) => ({ ...item }))
  );
}
</script>

<template>
  <div v-if="open && check" class="overlay" @click.self="emit('cancel')">
    <article class="dialog" role="dialog" aria-modal="true">
      <h2>Ежедневное ТО</h2>
      <p class="desc">Проверьте состояние ТС за {{ titleDate }}. Как в приёмке вахты: норма или неисправно.</p>
      <div v-for="item in items" :key="item.key" class="doc">
        <div class="doc-h"><span>{{ item.name }}</span></div>
        <div class="seg two">
          <button type="button" class="y" :class="{ on: item.st === 'ok' }" :disabled="busy" @click="setCheck(item, 'ok')">Норма</button>
          <button type="button" class="n" :class="{ on: item.st === 'bad' }" :disabled="busy" @click="setCheck(item, 'bad')">Неисправно</button>
        </div>
        <input
          v-if="item.st === 'bad'"
          v-model="item.note"
          class="chk-note"
          type="text"
          :disabled="busy"
          placeholder="Что именно не так"
        />
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <template v-if="confirmSkip">
        <p class="warn">Пропустить проверку за сегодня? В истории вахты это будет отмечено как пропуск.</p>
        <div class="actions">
          <button class="ghost" type="button" :disabled="busy" @click="confirmSkip = false">Назад</button>
          <button class="danger" type="button" :disabled="busy" @click="emit('skip')">{{ busy ? "…" : "Пропустить" }}</button>
        </div>
      </template>
      <template v-else>
        <button class="primary" type="button" :disabled="!filled || busy" @click="submit">
          {{ busy ? "Сохранение…" : "Сохранить проверку" }}
        </button>
        <div class="actions">
          <button class="ghost" type="button" :disabled="busy" @click="emit('cancel')">Закрыть</button>
          <button class="skip" type="button" :disabled="busy" @click="confirmSkip = true">Пропустить</button>
        </div>
      </template>
    </article>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 80;
  background: rgba(2, 6, 23, 0.72);
  display: grid;
  place-items: center;
  padding: 1rem;
}
.dialog {
  width: min(440px, 100%);
  max-height: min(92vh, 760px);
  overflow: auto;
  display: grid;
  gap: 0.65rem;
  padding: 1.05rem;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: #0f172a;
  box-shadow: var(--shadow);
}
h2 { margin: 0; }
.desc, .warn { margin: 0; color: var(--text-muted); font-size: 0.88rem; }
.warn { color: #fcd34d; }
.doc {
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 12px;
}
.doc-h { font-weight: 600; }
.seg {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border: 1.5px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  margin-top: 10px;
}
.seg button { border: 0; background: transparent; min-height: 46px; color: inherit; }
.seg button + button { border-left: 1.5px solid var(--border); }
.seg button.on.y { background: rgba(34, 197, 94, 0.16); color: #86efac; font-weight: 700; }
.seg button.on.n { background: rgba(239, 68, 68, 0.16); color: #fca5a5; font-weight: 700; }
.chk-note {
  margin-top: 10px;
  width: 100%;
  min-height: 44px;
  border: 1.5px solid var(--border);
  border-radius: 12px;
  background: #111827;
  color: inherit;
  font: inherit;
  padding: 8px 12px;
}
.primary, .ghost, .skip, .danger {
  border-radius: 10px;
  min-height: 44px;
  padding: 0.55rem 0.8rem;
}
.primary {
  border: none;
  background: var(--primary-strong, #2563eb);
  color: #fff;
  font-weight: 700;
}
.primary:disabled { opacity: 0.45; }
.ghost {
  background: transparent;
  color: #bfdbfe;
  border: 1px solid var(--border-strong, #334155);
}
.skip, .danger {
  border: 1px solid #fca5a5;
  background: transparent;
  color: #fca5a5;
  font-weight: 600;
}
.danger { background: #7f1d1d; color: #fff; }
.actions { display: flex; gap: 0.5rem; justify-content: space-between; }
.error { margin: 0; color: #fca5a5; }
</style>
