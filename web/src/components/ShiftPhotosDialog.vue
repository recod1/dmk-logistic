<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";

type VehicleSlot = "front" | "rear" | "left" | "right";

const VEHICLE_STEPS: Array<{ key: VehicleSlot; label: string }> = [
  { key: "front", label: "Спереди" },
  { key: "rear", label: "Сзади" },
  { key: "left", label: "Слева" },
  { key: "right", label: "Справа" }
];

const props = defineProps<{
  open: boolean;
  mode: "start" | "finish";
  uploading: boolean;
}>();

const emit = defineEmits<{
  cancel: [];
  confirm: [payload: { vehicle: Record<VehicleSlot, File>; waybill: File[] }];
}>();

const cameraInputRef = ref<HTMLInputElement | null>(null);
const galleryInputRef = ref<HTMLInputElement | null>(null);
const stepIndex = ref(0);
const vehicleFiles = ref<Partial<Record<VehicleSlot, File>>>({});
const waybillFiles = ref<File[]>([]);
const previewUrl = ref("");

const steps = computed(() => {
  const items: Array<{ key: VehicleSlot | "waybill"; label: string }> = VEHICLE_STEPS.map((item) => ({
    key: item.key,
    label: `Транспорт · ${item.label}`
  }));
  if (props.mode === "start") {
    items.push({ key: "waybill", label: "Путевой лист" });
  }
  return items;
});

const current = computed(() => steps.value[stepIndex.value] ?? steps.value[0]);
const isWaybill = computed(() => current.value?.key === "waybill");
const isLast = computed(() => stepIndex.value >= steps.value.length - 1);

const currentFile = computed(() => {
  if (!current.value) {
    return null;
  }
  if (current.value.key === "waybill") {
    return waybillFiles.value[waybillFiles.value.length - 1] ?? null;
  }
  return vehicleFiles.value[current.value.key] ?? null;
});

watch(
  () => props.open,
  (open) => {
    if (open) {
      stepIndex.value = 0;
      vehicleFiles.value = {};
      waybillFiles.value = [];
    }
  }
);

watch(
  currentFile,
  (file) => {
    if (previewUrl.value) {
      URL.revokeObjectURL(previewUrl.value);
      previewUrl.value = "";
    }
    previewUrl.value = file ? URL.createObjectURL(file) : "";
  }
);

onUnmounted(() => {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value);
  }
});

const canContinue = computed(() => Boolean(currentFile.value) && !props.uploading);
const title = computed(() => (props.mode === "start" ? "Начать вахту" : "Закончить вахту"));

function onFileChange(ev: Event): void {
  const input = ev.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file || !current.value) {
    return;
  }
  if (current.value.key === "waybill") {
    waybillFiles.value = [file];
    return;
  }
  vehicleFiles.value = { ...vehicleFiles.value, [current.value.key]: file };
}

function triggerCamera(): void {
  cameraInputRef.value?.click();
}

function triggerGallery(): void {
  galleryInputRef.value?.click();
}

function goNext(): void {
  if (!canContinue.value) {
    return;
  }
  if (!isLast.value) {
    stepIndex.value += 1;
    return;
  }
  const vehicle = vehicleFiles.value;
  if (!vehicle.front || !vehicle.rear || !vehicle.left || !vehicle.right) {
    return;
  }
  if (props.mode === "start" && !waybillFiles.value.length) {
    return;
  }
  emit("confirm", {
    vehicle: {
      front: vehicle.front,
      rear: vehicle.rear,
      left: vehicle.left,
      right: vehicle.right
    },
    waybill: waybillFiles.value
  });
}
</script>

<template>
  <div v-if="open" class="overlay" @click.self="emit('cancel')">
    <article class="dialog" role="dialog" aria-modal="true">
      <h2>{{ title }}</h2>
      <p class="step">Шаг {{ stepIndex + 1 }} из {{ steps.length }} · {{ current?.label }}</p>
      <p class="desc">
        {{
          isWaybill
            ? "Сделайте фото путевого листа."
            : "Сфотографируйте транспорт с этой стороны."
        }}
      </p>
      <input
        ref="cameraInputRef"
        type="file"
        accept="image/*"
        capture="environment"
        class="hidden-input"
        @change="onFileChange"
      />
      <input ref="galleryInputRef" type="file" accept="image/*" class="hidden-input" @change="onFileChange" />
      <img v-if="previewUrl" class="preview" :src="previewUrl" alt="Превью" />
      <button class="primary" type="button" :disabled="uploading" @click="triggerCamera">Сделать фото</button>
      <button class="secondary" type="button" :disabled="uploading" @click="triggerGallery">Выбрать из галереи</button>
      <div class="actions">
        <button class="primary" type="button" :disabled="!canContinue" @click="goNext">
          {{ isLast ? (uploading ? "Отправка…" : "Готово") : "Далее" }}
        </button>
        <button class="ghost" type="button" :disabled="uploading" @click="emit('cancel')">Отмена</button>
      </div>
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
  width: min(420px, 100%);
  display: grid;
  gap: 0.65rem;
  padding: 1.05rem;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: #0f172a;
  box-shadow: var(--shadow);
}
h2 {
  margin: 0;
}
.step,
.desc {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.88rem;
}
.hidden-input {
  display: none;
}
.preview {
  width: 100%;
  max-height: 220px;
  object-fit: cover;
  border-radius: 12px;
  border: 1px solid var(--border);
}
.primary,
.secondary,
.ghost {
  border: none;
  border-radius: 10px;
  padding: 0.55rem 0.8rem;
  color: #fff;
}
.primary {
  background: var(--primary-strong);
}
.secondary {
  background: #334155;
}
.ghost {
  background: transparent;
  color: #bfdbfe;
  border: 1px solid var(--border-strong);
}
.primary:disabled,
.secondary:disabled {
  opacity: 0.45;
}
.actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}
</style>
