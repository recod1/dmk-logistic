<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { PROBLEM_CHOICES, RETURN_WARNING, type IncidentKind } from "../routeIncidents";

const props = defineProps<{
  open: boolean;
  busy: boolean;
  canReturn: boolean;
  initialKind?: IncidentKind | "";
  unloadingPoints?: Array<{ id: number; label: string }>;
}>();

const emit = defineEmits<{
  cancel: [];
  submit: [
    payload: {
      kind: IncidentKind;
      comment: string;
      cargo_name: string;
      quantity: string;
      files: File[];
      point_id?: number;
    }
  ];
}>();

const kind = ref<IncidentKind | "">("");
const comment = ref("");
const cargoName = ref("");
const quantity = ref("");
const files = ref<File[]>([]);
const pointId = ref<number | null>(null);
const galleryRef = ref<HTMLInputElement | null>(null);
const cameraRef = ref<HTMLInputElement | null>(null);
const localError = ref("");
const unloadingPoints = computed(() => props.unloadingPoints || []);
const choice = computed(() => PROBLEM_CHOICES.find((item) => item.kind === kind.value) || null);
const isReturn = computed(() => kind.value === "return");
const needPointPick = computed(() => isReturn.value && unloadingPoints.value.length > 1);
const visibleChoices = computed(() => PROBLEM_CHOICES);

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      kind.value = props.initialKind || "";
      comment.value = "";
      cargoName.value = "";
      quantity.value = "";
      files.value = [];
      localError.value = "";
      pointId.value = unloadingPoints.value.length === 1 ? unloadingPoints.value[0].id : null;
    }
  }
);

watch(kind, (value) => {
  if (value !== "return") {
    return;
  }
  if (unloadingPoints.value.length === 1) {
    pointId.value = unloadingPoints.value[0].id;
  }
});

function onFiles(event: Event): void {
  const input = event.target as HTMLInputElement;
  const list = input.files ? Array.from(input.files) : [];
  if (list.length) {
    files.value = [...files.value, ...list].slice(0, 10);
  }
  input.value = "";
}

function removeFile(index: number): void {
  files.value.splice(index, 1);
}

function submit(): void {
  if (!kind.value || !choice.value) {
    localError.value = "Выберите проблему";
    return;
  }
  const text = comment.value.trim();
  if (choice.value.needsReason && !text) {
    localError.value = isReturn.value
      ? "Укажите причину возврата, количество и наименование груза"
      : "Укажите причину";
    return;
  }
  if (isReturn.value && (!cargoName.value.trim() || !quantity.value.trim())) {
    localError.value = "Для возврата укажите количество и краткое наименование груза";
    return;
  }
  if (isReturn.value && unloadingPoints.value.length === 0) {
    localError.value = "Возврат доступен на точках выгрузки";
    return;
  }
  if (isReturn.value && unloadingPoints.value.length > 1 && !pointId.value) {
    localError.value = "Выберите точку выгрузки";
    return;
  }
  localError.value = "";
  emit("submit", {
    kind: kind.value,
    comment: text,
    cargo_name: cargoName.value.trim(),
    quantity: quantity.value.trim(),
    files: files.value,
    point_id: isReturn.value ? pointId.value || undefined : undefined
  });
}
</script>

<template>
  <div v-if="open" class="overlay" @click.self="emit('cancel')">
    <section class="sheet">
      <h2>Проблемы в рейсе</h2>
      <p class="hint">Сообщение уйдёт в чат рейса и уведомления логистам, администраторам и диспетчеру.</p>
      <div class="kinds">
        <button
          v-for="item in visibleChoices"
          :key="item.kind"
          type="button"
          class="kind"
          :class="{ active: kind === item.kind }"
          @click="kind = item.kind"
        >
          {{ item.label }}
        </button>
      </div>
      <template v-if="choice">
        <div v-if="needPointPick" class="points">
          <p class="hint">Выберите точку выгрузки</p>
          <button
            v-for="point in unloadingPoints"
            :key="point.id"
            type="button"
            class="kind"
            :class="{ active: pointId === point.id }"
            @click="pointId = point.id"
          >
            {{ point.label }}
          </button>
        </div>
        <label v-if="isReturn">
          Краткое наименование груза
          <input v-model="cargoName" placeholder="корма, питание, кофе, рыба…" />
        </label>
        <label v-if="isReturn">
          Количество паллет или коробок
          <input v-model="quantity" placeholder="например 4 паллеты" />
        </label>
        <label>
          {{ isReturn ? "Причина возврата и комментарий" : "Причина / комментарий" }}
          <textarea v-model="comment" rows="3" :placeholder="choice.needsReason ? 'Обязательно' : 'По желанию'" />
        </label>
        <p v-if="isReturn" class="warn">{{ RETURN_WARNING }}</p>
        <div v-if="isReturn" class="photos">
          <p class="hint">Фото возврата и документов, если они уже есть.</p>
          <div class="row">
            <button type="button" class="secondary" @click="galleryRef?.click()">Галерея</button>
            <button type="button" class="secondary" @click="cameraRef?.click()">Камера</button>
          </div>
          <input ref="galleryRef" type="file" accept="image/*" multiple hidden @change="onFiles" />
          <input ref="cameraRef" type="file" accept="image/*" capture="environment" hidden @change="onFiles" />
          <ul v-if="files.length" class="files">
            <li v-for="(file, idx) in files" :key="`${file.name}-${idx}`">
              {{ file.name }}
              <button type="button" class="ghost" @click="removeFile(idx)">×</button>
            </li>
          </ul>
        </div>
      </template>
      <p v-if="localError" class="error">{{ localError }}</p>
      <div class="actions">
        <button type="button" class="primary" :disabled="busy || !kind" @click="submit">Отправить</button>
        <button type="button" class="ghost" :disabled="busy" @click="emit('cancel')">Отмена</button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 40;
  background: rgba(2, 6, 23, 0.72);
  display: grid;
  align-items: end;
  padding: 0.75rem;
}
.sheet {
  background: var(--bg-elevated);
  border: 1px solid var(--border-strong);
  border-radius: 16px;
  padding: 0.9rem;
  display: grid;
  gap: 0.55rem;
  max-height: 88vh;
  overflow: auto;
}
h2 {
  margin: 0;
  font-size: 1.05rem;
}
.hint {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.85rem;
}
.warn {
  margin: 0;
  color: #fecaca;
  font-weight: 650;
  line-height: 1.35;
}
.kinds,
.points {
  display: grid;
  gap: 0.35rem;
}
.kind {
  text-align: left;
  border: 1px solid var(--border-strong);
  border-radius: 10px;
  background: var(--surface);
  color: var(--text);
  padding: 0.5rem 0.7rem;
}
.kind.active {
  border-color: #60a5fa;
  background: var(--primary-soft);
}
label {
  display: grid;
  gap: 0.28rem;
  font-size: 0.82rem;
  color: var(--text-label);
}
input,
textarea {
  border-radius: 10px;
  border: 1px solid var(--border-strong);
  background: var(--bg-elevated);
  color: var(--text);
  padding: 0.5rem 0.62rem;
  font: inherit;
}
.row,
.actions {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}
.files {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.2rem;
  font-size: 0.82rem;
}
.error {
  color: #fca5a5;
  margin: 0;
}
.primary {
  border: none;
  border-radius: 10px;
  background: var(--success-strong);
  color: #fff;
  padding: 0.5rem 0.8rem;
}
.secondary,
.ghost {
  border: 1px solid var(--border-strong);
  border-radius: 10px;
  background: transparent;
  color: #dbeafe;
  padding: 0.4rem 0.7rem;
}
</style>
