<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from "vue";

import { fetchShiftImageBlob } from "../api";
import { toDatetimeLocalValue } from "../datetimeLocal";
import { stampShiftPhoto } from "../shiftPhotoStamp";
import {
  ALL_SLOTS,
  CAB_SLOTS,
  KIND_META,
  METER_SLOTS,
  PHASE_NAME,
  STEPS,
  TRUCK_SLOTS,
  analyseShift,
  diffNum,
  docExp,
  ensurePhase,
  expStatus,
  fmtD,
  fmtDT,
  fmtNum,
  fuelStats,
  reportText,
  slotLabel,
  stepDone,
  uid,
  type ShiftCheck,
  type ShiftDoc,
  type ShiftPhase,
  type ShiftPhasePayload,
  type ShiftRefuel,
  type ShiftWorkflow
} from "../shiftInspection";
import type { DriverShiftDetails } from "../types";

const props = defineProps<{
  shift: DriverShiftDetails | null;
  authToken: string;
  loading?: boolean;
  error?: string;
  busy?: boolean;
  readOnly?: boolean;
}>();

const emit = defineEmits<{
  back: [];
  save: [payload: Record<string, unknown>];
  uploadPhoto: [payload: { slot: string; phase: ShiftPhase; file: Blob; quality?: string[] }];
  accept: [force: boolean];
  beginEnd: [];
  close: [force: boolean];
  cancelEnd: [];
  deleteDraft: [];
}>();

const phase = ref<ShiftPhase>("start");
const step = ref(0);
const driverName = ref("");
const truck = ref("");
const trailer = ref("");
const place = ref("");
const startedLocal = ref("");
const intake = ref<ShiftPhasePayload>(ensurePhase());
const handover = ref<ShiftPhasePayload | null>(null);
const refuels = ref<ShiftRefuel[]>([]);
const thumbs = ref<Record<number, string>>({});
const pendingSlot = ref("");
const busySlot = ref("");
const viewer = ref<{ title: string; url: string } | null>(null);
const qualityAsk = ref<{ slot: string; blob: Blob; issues: string[]; url: string } | null>(null);
const confirmAsk = ref<{ text: string; ok: string; action: "accept" | "close" | "cancelEnd" | "delete" } | null>(null);
const toastText = ref("");
const cameraRef = ref<HTMLInputElement | null>(null);
const galleryRef = ref<HTMLInputElement | null>(null);
const sigCanvas = ref<HTMLCanvasElement | null>(null);
const newDocName = ref("");
let saveTimer: number | null = null;
let toastTimer: number | null = null;
let hydrating = false;

const workflow = computed<ShiftWorkflow>(() => {
  const raw = (props.shift?.workflow_status || "").trim();
  if (raw === "draft" || raw === "active" || raw === "closing" || raw === "closed") return raw;
  return props.shift?.status === "ended" ? "closed" : "active";
});

const payload = computed(() => (phase.value === "end" ? handover.value || ensurePhase() : intake.value));

const images = computed(() =>
  (props.shift?.images || []).filter((item) => (item.phase || (String(item.kind).startsWith("end") ? "end" : "start")) === phase.value)
);

const photoBySlot = computed(() => {
  const map: Record<string, { id: number; slot: string }> = {};
  for (const img of images.value) {
    if (img.slot) map[img.slot] = { id: img.id, slot: img.slot };
  }
  return map;
});

const photoKeys = computed(() => Object.keys(photoBySlot.value));
const isRO = computed(() => {
  if (props.readOnly) return true;
  return phase.value === "start" ? workflow.value !== "draft" : workflow.value !== "closing";
});
const issues = computed(() =>
  analyseShift({
    driver_name: driverName.value,
    truck: truck.value,
    intake: intake.value,
    handover: handover.value,
    photoKeys: photoKeys.value,
    phase: phase.value
  })
);
const badCount = computed(() => issues.value.filter((item) => item[0] === "bad").length);
const fuel = computed(() => fuelStats(intake.value, handover.value, refuels.value));
const hasHandover = computed(() => Boolean(handover.value) || workflow.value === "closing" || workflow.value === "closed");

const TRUCK_SVG =
  '<svg viewBox="0 0 60 160" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><rect x="12" y="6" width="36" height="30" rx="7"/><path d="M16 14h28" /><rect x="7" y="16" width="5" height="9" rx="1.5"/><rect x="48" y="16" width="5" height="9" rx="1.5"/><path d="M26 36v6h8v-6"/><rect x="8" y="42" width="44" height="112" rx="3"/><path d="M8 140h44M30 42v98" stroke-dasharray="3 4"/></svg>';

function toast(text: string): void {
  toastText.value = text;
  if (toastTimer) window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => {
    toastText.value = "";
    toastTimer = null;
  }, 2200);
}

function hydrate(resetPosition = true): void {
  const shift = props.shift;
  if (!shift) return;
  hydrating = true;
  driverName.value = shift.driver_full_name || "";
  truck.value = shift.truck || "";
  trailer.value = shift.trailer || "";
  place.value = shift.place || "";
  startedLocal.value = shift.started_at ? toDatetimeLocalValue(new Date(shift.started_at)) : toDatetimeLocalValue(new Date());
  intake.value = ensurePhase(shift.intake || undefined);
  handover.value = shift.handover ? ensurePhase(shift.handover) : null;
  refuels.value = Array.isArray(shift.refuels) ? shift.refuels : [];
  if (!intake.value.time) intake.value.time = startedLocal.value;
  const wf = workflow.value;
  if (resetPosition) {
    phase.value = wf === "closing" || wf === "closed" ? "end" : "start";
  }
  if (phase.value === "end" && !handover.value) {
    handover.value = ensurePhase();
  }
  if (resetPosition) {
    step.value = [0, 1, 2].find((i) => !isStepDone(i)) ?? 3;
  }
  hydrating = false;
}

function isStepDone(index: number): boolean {
  return stepDone({
    driver_name: driverName.value,
    truck: truck.value,
    payload: payload.value,
    photoKeys: photoKeys.value,
    phase: phase.value,
    step: index,
    workflow: workflow.value
  });
}

function scheduleSave(): void {
  if (hydrating || isRO.value) return;
  if (saveTimer) window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(() => {
    saveTimer = null;
    flushSave();
  }, 700);
}

function flushSave(): void {
  if (isRO.value || !props.shift) return;
  const body: Record<string, unknown> = {
    driver_name: driverName.value,
    truck: truck.value,
    trailer: trailer.value,
    place: place.value
  };
  if (phase.value === "start") {
    body.started_at = new Date(startedLocal.value).toISOString();
    body.intake = { ...intake.value, time: startedLocal.value, place: place.value };
  } else if (handover.value) {
    body.handover = handover.value;
  }
  body.refuels = refuels.value;
  emit("save", body);
}

watch(
  () => [props.shift?.id, props.shift?.workflow_status] as const,
  () => hydrate(true),
  { immediate: true }
);

watch(
  () => [props.shift?.id, props.authToken, props.shift?.images?.length] as const,
  async () => {
    Object.values(thumbs.value).forEach((url) => URL.revokeObjectURL(url));
    thumbs.value = {};
    const shift = props.shift;
    if (!shift || !props.authToken) return;
    const next: Record<number, string> = {};
    for (const img of shift.images || []) {
      try {
        const blob = await fetchShiftImageBlob(props.authToken, img.id, { thumbnail: true });
        next[img.id] = URL.createObjectURL(blob);
      } catch {
        // skip
      }
    }
    thumbs.value = next;
  },
  { immediate: true }
);

onUnmounted(() => {
  if (saveTimer) window.clearTimeout(saveTimer);
  if (toastTimer) window.clearTimeout(toastTimer);
  Object.values(thumbs.value).forEach((url) => URL.revokeObjectURL(url));
  if (viewer.value?.url) URL.revokeObjectURL(viewer.value.url);
});

function setPhase(next: ShiftPhase): void {
  if (next === "end" && !handover.value) return;
  phase.value = next;
  step.value = [0, 1, 2].find((i) => !isStepDone(i)) ?? 3;
  void nextTick(() => initSign());
}

function setStep(index: number): void {
  step.value = index;
  void nextTick(() => initSign());
}

function shoot(slot: string): void {
  if (isRO.value || props.busy) return;
  pendingSlot.value = slot;
  cameraRef.value?.click();
}

async function onFilePicked(ev: Event): Promise<void> {
  const input = ev.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  const slot = pendingSlot.value;
  pendingSlot.value = "";
  if (!file || !slot) return;
  busySlot.value = slot;
  try {
    const { blob, issues } = await stampShiftPhoto(file, `${PHASE_NAME[phase.value]} · ${slotLabel(slot)}`, truck.value);
    if (issues.length) {
      qualityAsk.value = { slot, blob, issues, url: URL.createObjectURL(blob) };
      return;
    }
    await sendPhoto(slot, blob, []);
  } catch (error) {
    toast((error as Error).message || "Не удалось обработать фото");
  } finally {
    busySlot.value = "";
  }
}

async function sendPhoto(slot: string, blob: Blob, quality: string[]): Promise<void> {
  emit("uploadPhoto", { slot, phase: phase.value, file: blob, quality });
}

function keepQuality(): void {
  const ask = qualityAsk.value;
  if (!ask) return;
  URL.revokeObjectURL(ask.url);
  qualityAsk.value = null;
  void sendPhoto(ask.slot, ask.blob, ask.issues);
}

function retakeQuality(): void {
  const ask = qualityAsk.value;
  if (!ask) return;
  URL.revokeObjectURL(ask.url);
  qualityAsk.value = null;
  shoot(ask.slot);
}

function openPhoto(slot: string): void {
  const img = photoBySlot.value[slot];
  if (!img) return;
  const url = thumbs.value[img.id];
  viewer.value = { title: slotLabel(slot), url: url || "" };
}

function addDamage(): void {
  if (isRO.value) return;
  const id = uid();
  payload.value.damages.push({ id, note: "" });
  shoot(`dmg:${id}`);
  scheduleSave();
}

function removeDamage(id: string): void {
  payload.value.damages = payload.value.damages.filter((item) => item.id !== id);
  scheduleSave();
}

function setDocHas(doc: ShiftDoc, value: "y" | "n" | "x"): void {
  if (isRO.value) return;
  doc.has = doc.has === value ? null : value;
  scheduleSave();
}

function addDoc(): void {
  const name = newDocName.value.trim();
  if (!name) return;
  payload.value.docs.push({
    id: uid(),
    name,
    needs_exp: true,
    has: "y",
    exp: "",
    kind: "",
    d1: "",
    d2: "",
    custom: true
  });
  newDocName.value = "";
  scheduleSave();
}

function setCheck(item: ShiftCheck, value: "ok" | "bad"): void {
  if (isRO.value) return;
  item.st = item.st === value ? null : value;
  scheduleSave();
}

function markRestOk(): void {
  payload.value.checks.forEach((item) => {
    if (item.st == null) item.st = "ok";
  });
  scheduleSave();
}

function initSign(): void {
  const c = sigCanvas.value;
  if (!c || isRO.value) return;
  const dpr = window.devicePixelRatio || 1;
  const w = c.clientWidth;
  const h = c.clientHeight;
  c.width = Math.round(w * dpr);
  c.height = Math.round(h * dpr);
  const ctx = c.getContext("2d");
  if (!ctx) return;
  ctx.scale(dpr, dpr);
  ctx.lineWidth = 2.6;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.strokeStyle = "#17212C";
  ctx.fillStyle = "#17212C";
  let on = false;
  let len = 0;
  const pt = (e: PointerEvent) => {
    const r = c.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top] as const;
  };
  c.onpointerdown = (e) => {
    e.preventDefault();
    on = true;
    c.setPointerCapture(e.pointerId);
    const [a, b] = pt(e);
    ctx.beginPath();
    ctx.moveTo(a, b);
  };
  c.onpointermove = (e) => {
    if (!on) return;
    const [a, b] = pt(e);
    ctx.lineTo(a, b);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(a, b);
    len += 1;
  };
  const end = () => {
    if (!on) return;
    on = false;
    if (len < 3) return;
    const out = document.createElement("canvas");
    out.width = 480;
    out.height = Math.round(480 * h / Math.max(1, w));
    const ox = out.getContext("2d");
    if (!ox) return;
    ox.fillStyle = "#fff";
    ox.fillRect(0, 0, out.width, out.height);
    ox.drawImage(c, 0, 0, out.width, out.height);
    out.toBlob((blob) => {
      if (!blob) return;
      payload.value.signed_at = new Date().toISOString();
      emit("uploadPhoto", { slot: "sign", phase: phase.value, file: blob });
      scheduleSave();
    }, "image/png");
  };
  c.onpointerup = end;
  c.onpointercancel = end;
}

async function copyReport(): Promise<void> {
  const text = reportText({
    driver_name: driverName.value,
    truck: truck.value,
    trailer: trailer.value,
    intake: intake.value,
    handover: handover.value,
    refuels: refuels.value
  });
  try {
    await navigator.clipboard.writeText(text);
    toast("Отчёт скопирован");
  } catch {
    toast("Не удалось скопировать");
  }
}

function askAccept(): void {
  if (!photoBySlot.value.sign && !payload.value.signed_at) {
    toast("Поставьте подпись в конце итога");
    setStep(3);
    return;
  }
  confirmAsk.value = {
    text: badCount.value ? `Есть замечания: ${badCount.value}. Всё равно принять ТС и начать вахту?` : "Принять ТС и начать вахту?",
    ok: "Принять",
    action: "accept"
  };
}

function askClose(): void {
  if (!photoBySlot.value.sign && !payload.value.signed_at) {
    toast("Поставьте подпись в конце итога");
    setStep(3);
    return;
  }
  confirmAsk.value = {
    text: badCount.value ? `Есть замечания: ${badCount.value}. Всё равно сдать ТС и завершить вахту?` : "Сдать ТС и завершить вахту?",
    ok: "Сдать ТС",
    action: "close"
  };
}

function confirmModal(ok: boolean): void {
  const ask = confirmAsk.value;
  confirmAsk.value = null;
  if (!ok || !ask) return;
  if (ask.action === "accept") emit("accept", badCount.value > 0);
  if (ask.action === "close") emit("close", badCount.value > 0);
  if (ask.action === "cancelEnd") emit("cancelEnd");
  if (ask.action === "delete") emit("deleteDraft");
}

function addRefuel(): void {
  refuels.value.push({ id: uid(), time: toDatetimeLocalValue(new Date()), liters: "", odo: "", place: "" });
  scheduleSave();
}

watch(step, () => {
  if (step.value === 3) void nextTick(() => initSign());
});
</script>

<template>
  <section class="inspect">
    <div class="top">
      <div class="top-row">
        <button class="iconbtn" type="button" aria-label="К списку вахт" @click="emit('back')">←</button>
        <div class="top-title">{{ truck || "Новая вахта" }}</div>
        <span class="pill" :class="workflow">{{ PHASE_NAME[phase] }}</span>
      </div>
      <div v-if="hasHandover" class="phase">
        <button type="button" :class="{ on: phase === 'start' }" @click="setPhase('start')">Приёмка ТС</button>
        <button type="button" :class="{ on: phase === 'end' }" :disabled="!handover" @click="setPhase('end')">Сдача ТС</button>
      </div>
      <nav class="steps">
        <button
          v-for="(title, index) in STEPS"
          :key="title"
          type="button"
          class="step"
          :class="{ on: index === step, done: index !== step && isStepDone(index) }"
          @click="setStep(index)"
        >
          <b>{{ index + 1 }}</b>{{ title }}
        </button>
      </nav>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading" class="muted">Загрузка…</p>

    <div v-if="step === 0" class="stack">
      <h2>{{ phase === "end" ? "Окончание вахты" : "Начало вахты" }}</h2>
      <div class="card stack">
        <label v-if="phase === 'start'" class="f">
          <span>Водитель, ФИО</span>
          <input v-model="driverName" type="text" :disabled="isRO" placeholder="Иванов Иван Иванович" @input="scheduleSave" />
        </label>
        <label class="f">
          <span>{{ phase === "end" ? "Окончание вахты" : "Начало вахты" }}</span>
          <input
            v-if="phase === 'start'"
            v-model="startedLocal"
            type="datetime-local"
            :disabled="isRO"
            @change="scheduleSave"
          />
          <input v-else v-model="payload.time" type="datetime-local" :disabled="isRO" @change="scheduleSave" />
        </label>
        <label class="f">
          <span>{{ phase === "end" ? "Место сдачи" : "Место приёмки" }}</span>
          <input
            v-if="phase === 'start'"
            v-model="place"
            type="text"
            :disabled="isRO"
            placeholder="База, город"
            @input="scheduleSave"
          />
          <input v-else v-model="payload.place" type="text" :disabled="isRO" placeholder="База, город" @input="scheduleSave" />
        </label>
      </div>
      <h2>Транспортное средство</h2>
      <div v-if="phase === 'start'" class="card stack">
        <label class="f">
          <span>Тягач</span>
          <input v-model="truck" class="plate" type="text" :disabled="isRO" placeholder="А123ВС 77" @input="scheduleSave" />
        </label>
        <label class="f">
          <span>Прицеп-рефрижератор</span>
          <input v-model="trailer" class="plate" type="text" :disabled="isRO" placeholder="АВ1234 77" @input="scheduleSave" />
        </label>
      </div>
      <div v-else class="card">
        <dl class="kv">
          <dt>Водитель</dt><dd>{{ driverName || "—" }}</dd>
          <dt>Тягач</dt><dd>{{ truck || "—" }}</dd>
          <dt>Прицеп</dt><dd>{{ trailer || "—" }}</dd>
          <dt>Принята</dt><dd>{{ fmtDT(shift?.started_at) }}</dd>
        </dl>
      </div>
    </div>

    <div v-else-if="step === 1" class="stack">
      <h2>Машина со всех сторон</h2>
      <p class="muted small">Снято обязательных: {{ ALL_SLOTS.filter((s) => s.req && photoBySlot[s.k]).length }} из {{ ALL_SLOTS.filter((s) => s.req).length }}.</p>
      <div class="map">
        <button v-for="slot in TRUCK_SLOTS.filter((s) => s.k === 'fl')" :key="slot.k" type="button" class="slot" :class="{ has: photoBySlot[slot.k], req: slot.req, busy: busySlot === slot.k, tall: false }" @click="photoBySlot[slot.k] ? openPhoto(slot.k) : shoot(slot.k)">
          <img v-if="photoBySlot[slot.k] && thumbs[photoBySlot[slot.k].id]" :src="thumbs[photoBySlot[slot.k].id]" :alt="slot.n" />
          <span class="cap">{{ slot.n }}</span>
        </button>
        <button type="button" class="slot" :class="{ has: photoBySlot.front, req: true, busy: busySlot === 'front' }" @click="photoBySlot.front ? openPhoto('front') : shoot('front')">
          <img v-if="photoBySlot.front && thumbs[photoBySlot.front.id]" :src="thumbs[photoBySlot.front.id]" alt="Спереди" />
          <span class="cap">Спереди</span>
        </button>
        <button type="button" class="slot" :class="{ has: photoBySlot.fr, busy: busySlot === 'fr' }" @click="photoBySlot.fr ? openPhoto('fr') : shoot('fr')">
          <img v-if="photoBySlot.fr && thumbs[photoBySlot.fr.id]" :src="thumbs[photoBySlot.fr.id]" alt="Спереди справа" />
          <span class="cap">Спереди справа</span>
        </button>
        <button type="button" class="slot tall" :class="{ has: photoBySlot.left, req: true, busy: busySlot === 'left' }" @click="photoBySlot.left ? openPhoto('left') : shoot('left')">
          <img v-if="photoBySlot.left && thumbs[photoBySlot.left.id]" :src="thumbs[photoBySlot.left.id]" alt="Левый борт" />
          <span class="cap">Левый борт</span>
        </button>
        <div class="truck" v-html="TRUCK_SVG" />
        <button type="button" class="slot tall" :class="{ has: photoBySlot.right, req: true, busy: busySlot === 'right' }" @click="photoBySlot.right ? openPhoto('right') : shoot('right')">
          <img v-if="photoBySlot.right && thumbs[photoBySlot.right.id]" :src="thumbs[photoBySlot.right.id]" alt="Правый борт" />
          <span class="cap">Правый борт</span>
        </button>
        <button type="button" class="slot" :class="{ has: photoBySlot.rl, busy: busySlot === 'rl' }" @click="photoBySlot.rl ? openPhoto('rl') : shoot('rl')">
          <img v-if="photoBySlot.rl && thumbs[photoBySlot.rl.id]" :src="thumbs[photoBySlot.rl.id]" alt="Сзади слева" />
          <span class="cap">Сзади слева</span>
        </button>
        <button type="button" class="slot" :class="{ has: photoBySlot.rear, req: true, busy: busySlot === 'rear' }" @click="photoBySlot.rear ? openPhoto('rear') : shoot('rear')">
          <img v-if="photoBySlot.rear && thumbs[photoBySlot.rear.id]" :src="thumbs[photoBySlot.rear.id]" alt="Сзади" />
          <span class="cap">Сзади</span>
        </button>
        <button type="button" class="slot" :class="{ has: photoBySlot.rr, busy: busySlot === 'rr' }" @click="photoBySlot.rr ? openPhoto('rr') : shoot('rr')">
          <img v-if="photoBySlot.rr && thumbs[photoBySlot.rr.id]" :src="thumbs[photoBySlot.rr.id]" alt="Сзади справа" />
          <span class="cap">Сзади справа</span>
        </button>
      </div>
      <h2>Салон</h2>
      <div class="pair">
        <button v-for="slot in CAB_SLOTS" :key="slot.k" type="button" class="slot" :class="{ has: photoBySlot[slot.k], req: true, busy: busySlot === slot.k }" @click="photoBySlot[slot.k] ? openPhoto(slot.k) : shoot(slot.k)">
          <img v-if="photoBySlot[slot.k] && thumbs[photoBySlot[slot.k].id]" :src="thumbs[photoBySlot[slot.k].id]" :alt="slot.n" />
          <span class="cap">{{ slot.n }}</span>
        </button>
      </div>
      <div v-for="slot in METER_SLOTS" :key="slot.k" class="card meter">
        <button type="button" class="slot" :class="{ has: photoBySlot[slot.k], req: true, busy: busySlot === slot.k }" @click="photoBySlot[slot.k] ? openPhoto(slot.k) : shoot(slot.k)">
          <img v-if="photoBySlot[slot.k] && thumbs[photoBySlot[slot.k].id]" :src="thumbs[photoBySlot[slot.k].id]" :alt="slot.n" />
          <span class="cap">{{ slot.n }}</span>
        </button>
        <label class="f">
          <span>{{ slot.k === "odo" ? "Пробег, км" : slot.k === "fuel" ? "Остаток, л" : "Моточасы" }}</span>
          <input
            :value="slot.k === 'odo' ? payload.odo : slot.k === 'fuel' ? payload.fuel : payload.reefer"
            :disabled="isRO"
            inputmode="decimal"
            @input="(e) => { const v = (e.target as HTMLInputElement).value; if (slot.k === 'odo') payload.odo = v.replace(/\D/g, ''); else if (slot.k === 'fuel') payload.fuel = v.replace(',', '.').replace(/[^\d.]/g, ''); else payload.reefer = v.replace(',', '.').replace(/[^\d.]/g, ''); scheduleSave(); }"
          />
          <p v-if="phase === 'end'" class="muted small">На приёмке: {{ slot.k === "odo" ? fmtNum(intake.odo) : slot.k === "fuel" ? fmtNum(intake.fuel) : fmtNum(intake.reefer) }}</p>
        </label>
      </div>
      <h2>Повреждения</h2>
      <p class="muted small">{{ phase === "end" ? "Сверьте с повреждениями приёмки. Новые сфотографируйте отдельно." : "Сколы, вмятины, трещины — всё, что уже есть на машине." }}</p>
      <div v-if="phase === 'end' && intake.damages.length" class="prev">
        <figure v-for="d in intake.damages" :key="d.id">
          <figcaption>{{ d.note || "без описания" }}</figcaption>
        </figure>
      </div>
      <div v-for="d in payload.damages" :key="d.id" class="dmg card">
        <button type="button" class="slot" :class="{ has: photoBySlot['dmg:' + d.id], busy: busySlot === 'dmg:' + d.id }" @click="photoBySlot['dmg:' + d.id] ? openPhoto('dmg:' + d.id) : shoot('dmg:' + d.id)">
          <img v-if="photoBySlot['dmg:' + d.id] && thumbs[photoBySlot['dmg:' + d.id].id]" :src="thumbs[photoBySlot['dmg:' + d.id].id]" alt="Повреждение" />
          <span class="cap">Повреждение</span>
        </button>
        <div>
          <label class="f"><span>Что и где</span><input v-model="d.note" type="text" :disabled="isRO" placeholder="Вмятина, правая дверь" @input="scheduleSave" /></label>
          <button v-if="!isRO" class="rm" type="button" @click="removeDamage(d.id)">Удалить</button>
        </div>
      </div>
      <button v-if="!isRO" class="btn sec" type="button" @click="addDamage">Сфотографировать повреждение</button>
    </div>

    <div v-else-if="step === 2" class="stack">
      <h2>Сверка документов</h2>
      <p class="muted small">Отмечено «есть»: {{ payload.docs.filter((d) => d.has === "y").length }} из {{ payload.docs.length }}.</p>
      <div v-for="doc in payload.docs" :key="doc.id" class="doc">
        <div class="doc-h">
          <span>{{ doc.name }}</span>
          <span v-if="expStatus(doc)" class="pill" :class="expStatus(doc)?.c">{{ expStatus(doc)?.t }}</span>
        </div>
        <div class="seg">
          <button type="button" class="y" :class="{ on: doc.has === 'y' }" :disabled="isRO" @click="setDocHas(doc, 'y')">Есть</button>
          <button type="button" class="n" :class="{ on: doc.has === 'n' }" :disabled="isRO" @click="setDocHas(doc, 'n')">Нет</button>
          <button type="button" class="x" :class="{ on: doc.has === 'x' }" :disabled="isRO" @click="setDocHas(doc, 'x')">Не нужен</button>
        </div>
        <template v-if="doc.has === 'y'">
          <label v-if="doc.kind && KIND_META[doc.kind]" class="f"><span>{{ KIND_META[doc.kind].l1 }}</span><input v-model="doc.d1" type="date" :disabled="isRO" @change="scheduleSave" /></label>
          <label v-if="doc.kind && KIND_META[doc.kind]" class="f"><span>{{ KIND_META[doc.kind].l2 }}</span><input v-model="doc.d2" type="date" :disabled="isRO" @change="scheduleSave" /></label>
          <label v-else-if="doc.needs_exp" class="f"><span>Действует до</span><input v-model="doc.exp" type="date" :disabled="isRO" @change="scheduleSave" /></label>
          <button v-if="doc.kind" type="button" class="slot doc-photo" :class="{ has: photoBySlot['doc:' + doc.id] }" @click="photoBySlot['doc:' + doc.id] ? openPhoto('doc:' + doc.id) : shoot('doc:' + doc.id)">
            <img v-if="photoBySlot['doc:' + doc.id] && thumbs[photoBySlot['doc:' + doc.id].id]" :src="thumbs[photoBySlot['doc:' + doc.id].id]" :alt="doc.name" />
            <span class="cap">Фото документа</span>
          </button>
        </template>
        <button v-if="doc.custom && !isRO" class="rm" type="button" @click="payload.docs.splice(payload.docs.indexOf(doc), 1); scheduleSave()">Убрать из списка</button>
      </div>
      <div v-if="!isRO" class="add">
        <input v-model="newDocName" type="text" placeholder="Другой документ, например CMR" />
        <button class="btn" type="button" @click="addDoc">Добавить</button>
      </div>
      <h2>Состояние и комплектность</h2>
      <p class="muted small">
        Проверено: {{ payload.checks.filter((c) => c.st != null).length }} из {{ payload.checks.length }}.
        <button v-if="!isRO" class="rm" type="button" @click="markRestOk">Отметить остальное как норму</button>
      </p>
      <div v-for="item in payload.checks" :key="item.id" class="doc">
        <div class="doc-h"><span>{{ item.name }}</span></div>
        <div class="seg two">
          <button type="button" class="y" :class="{ on: item.st === 'ok' }" :disabled="isRO" @click="setCheck(item, 'ok')">Норма</button>
          <button type="button" class="n" :class="{ on: item.st === 'bad' }" :disabled="isRO" @click="setCheck(item, 'bad')">Неисправно</button>
        </div>
        <input v-if="item.st === 'bad'" v-model="item.note" class="chk-note" type="text" :disabled="isRO" placeholder="Что именно не так" @input="scheduleSave" />
      </div>
    </div>

    <div v-else class="stack">
      <h2>Итог: {{ PHASE_NAME[phase].toLowerCase() }} ТС</h2>
      <section v-if="phase === 'end'" class="hero">
        <p>За вахту</p>
        <div class="delta">
          <div><b>{{ diffNum(intake.odo, payload.odo) == null ? "—" : fmtNum(diffNum(intake.odo, payload.odo)) + " км" }}</b><span class="small">пробег</span></div>
          <div><b>{{ diffNum(intake.reefer, payload.reefer) == null ? "—" : fmtNum(diffNum(intake.reefer, payload.reefer)) }}</b><span class="small">моточасы рефа</span></div>
          <div><b>{{ fuel.per100 == null ? "—" : fmtNum(fuel.per100) }}</b><span class="small">л/100 км</span></div>
        </div>
      </section>
      <ul class="issues">
        <li v-if="!issues.length" class="ok">Замечаний нет, машина {{ phase === "end" ? "сдана" : "принята" }} полностью</li>
        <li v-for="(item, idx) in issues" :key="idx" :class="item[0]">{{ item[1] }}</li>
      </ul>
      <h2>Сведения</h2>
      <div class="card">
        <dl class="kv">
          <dt>Водитель</dt><dd>{{ driverName || "—" }}</dd>
          <dt>Тягач</dt><dd>{{ truck || "—" }}</dd>
          <dt>Прицеп</dt><dd>{{ trailer || "—" }}</dd>
          <dt>{{ phase === "end" ? "Окончание" : "Начало" }}</dt><dd>{{ fmtDT(phase === "end" ? payload.time : startedLocal) }}</dd>
          <dt>Место</dt><dd>{{ (phase === "end" ? payload.place : place) || "—" }}</dd>
          <dt>Одометр</dt><dd>{{ fmtNum(payload.odo) }} км</dd>
          <dt>Топливо</dt><dd>{{ fmtNum(payload.fuel) }} л</dd>
          <dt>Моточасы рефа</dt><dd>{{ fmtNum(payload.reefer) }}</dd>
        </dl>
      </div>
      <h2>Подпись водителя</h2>
      <p class="muted small">Подписывая, водитель подтверждает данные {{ phase === "end" ? "сдачи" : "приёмки" }} ТС.</p>
      <div v-if="photoBySlot.sign" class="card">
        <img v-if="thumbs[photoBySlot.sign.id]" class="sig-img" :src="thumbs[photoBySlot.sign.id]" alt="Подпись" />
      </div>
      <div v-else-if="!isRO" class="sigwrap">
        <canvas ref="sigCanvas" id="sig" />
        <span class="sig-hint">Распишитесь пальцем</span>
      </div>
      <p v-else class="muted">Не подписано.</p>
      <div v-if="workflow !== 'draft'" class="card stack">
        <h2>Заправки за вахту</h2>
        <div v-for="item in refuels" :key="item.id" class="refuel">
          <input v-model="item.time" type="datetime-local" :disabled="isRO" @change="scheduleSave" />
          <input v-model="item.liters" placeholder="Литры" :disabled="isRO" @input="scheduleSave" />
          <input v-model="item.odo" placeholder="Одометр" :disabled="isRO" @input="scheduleSave" />
          <input v-model="item.place" placeholder="АЗС" :disabled="isRO" @input="scheduleSave" />
        </div>
        <button v-if="!isRO" class="btn sec" type="button" @click="addRefuel">Добавить заправку</button>
      </div>
      <button v-if="workflow === 'draft' && !readOnly" class="btn danger" type="button" @click="confirmAsk = { text: 'Удалить черновик вместе с фото?', ok: 'Удалить', action: 'delete' }">Удалить черновик</button>
      <button v-if="workflow === 'closing' && !readOnly" class="btn danger" type="button" @click="confirmAsk = { text: 'Отменить сдачу? Уже сделанные фото и отметки сохранятся.', ok: 'Отменить сдачу', action: 'cancelEnd' }">Отменить сдачу, вахта продолжается</button>
    </div>

    <div class="bar">
      <div class="in">
        <button v-if="step > 0 && step < 3" class="btn sec" type="button" @click="setStep(step - 1)">Назад</button>
        <button v-if="step < 3" class="btn" type="button" @click="setStep(step + 1)">Далее: {{ STEPS[step + 1].toLowerCase() }}</button>
        <template v-else>
          <button class="btn sec" type="button" @click="copyReport">Отчёт</button>
          <button v-if="phase === 'start' && workflow === 'draft' && !readOnly" class="btn" type="button" :disabled="busy" @click="askAccept">Принять ТС, начать вахту</button>
          <button v-else-if="phase === 'start' && workflow === 'active' && !readOnly" class="btn" type="button" :disabled="busy" @click="emit('beginEnd')">Сдать ТС</button>
          <button v-else-if="phase === 'end' && workflow === 'closing' && !readOnly" class="btn" type="button" :disabled="busy" @click="askClose">Сдать ТС, завершить вахту</button>
        </template>
      </div>
    </div>

    <input ref="cameraRef" class="hidden" type="file" accept="image/*" capture="environment" @change="onFilePicked" />
    <input ref="galleryRef" class="hidden" type="file" accept="image/*" @change="onFilePicked" />

    <div v-if="viewer" class="lb" @click.self="viewer = null">
      <p>{{ viewer.title }}</p>
      <img v-if="viewer.url" :src="viewer.url" :alt="viewer.title" />
      <button class="btn sec" type="button" @click="viewer = null">Закрыть</button>
    </div>
    <div v-if="qualityAsk" class="lb">
      <p>Фото лучше переснять</p>
      <ul><li v-for="item in qualityAsk.issues" :key="item">{{ item }}</li></ul>
      <img :src="qualityAsk.url" alt="Проверка фото" />
      <div class="row">
        <button class="btn sec" type="button" @click="keepQuality">Оставить так</button>
        <button class="btn" type="button" @click="retakeQuality">Переснять</button>
      </div>
    </div>
    <div v-if="confirmAsk" class="lb modal">
      <div class="mbox">
        <p>{{ confirmAsk.text }}</p>
        <div class="row">
          <button class="btn sec" type="button" @click="confirmModal(false)">Отмена</button>
          <button class="btn" type="button" @click="confirmModal(true)">{{ confirmAsk.ok }}</button>
        </div>
      </div>
    </div>
    <p v-if="toastText" class="toast">{{ toastText }}</p>
  </section>
</template>

<style scoped>
.inspect {
  --paper: var(--bg);
  --card: var(--surface);
  --ink: var(--text);
  --muted: var(--text-muted);
  --line: var(--border);
  --accent: var(--primary);
  --accent-ink: #fff;
  --ok: #22c55e;
  --ok-soft: rgba(34, 197, 94, 0.16);
  --warn: #f59e0b;
  --warn-soft: rgba(245, 158, 11, 0.16);
  --bad: #ef4444;
  --bad-soft: rgba(239, 68, 68, 0.16);
  --slot: var(--surface-2);
  color: var(--ink);
  padding-bottom: 5.5rem;
}
.top { position: sticky; top: 0; z-index: 4; background: var(--paper); margin: -0.2rem -0.2rem 0; padding: 0.4rem 0.2rem 0; }
.top-row { display: flex; align-items: center; gap: 8px; min-height: 44px; }
.iconbtn { width: 44px; height: 44px; border: 0; background: transparent; color: inherit; border-radius: 12px; }
.top-title { font-weight: 700; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.steps { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; padding: 8px 0 10px; border-bottom: 1px solid var(--line); }
.step { border: 0; background: transparent; padding: 6px 2px; border-radius: 10px; font-size: .8rem; color: var(--muted); display: flex; flex-direction: column; align-items: center; gap: 4px; }
.step b { width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; border: 1.5px solid var(--line); }
.step.on { color: var(--ink); font-weight: 600; }
.step.on b { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); }
.step.done b { background: var(--ok-soft); border-color: var(--ok); color: var(--ok); }
.phase { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 3px; margin-top: 6px; }
.phase button { border: 0; background: transparent; border-radius: 9px; min-height: 38px; font-weight: 600; color: var(--muted); }
.phase button.on { background: var(--accent); color: var(--accent-ink); }
.stack { display: grid; gap: 12px; }
h2 { font-size: 1.05rem; margin: 18px 0 4px; }
.muted { color: var(--muted); }
.small { font-size: .875rem; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 16px; }
.f { display: block; }
.f span { display: block; font-size: .875rem; color: var(--muted); margin-bottom: 6px; }
input, textarea { width: 100%; min-height: 52px; border: 1.5px solid var(--line); border-radius: 12px; background: var(--card); color: var(--ink); font: inherit; padding: 10px 14px; }
.plate { text-transform: uppercase; letter-spacing: .04em; font-weight: 600; }
.btn { display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%; min-height: 52px; border: 0; border-radius: 14px; background: var(--accent); color: var(--accent-ink); font-weight: 600; }
.btn.sec { background: var(--card); color: var(--ink); border: 1.5px solid var(--line); }
.btn.danger { background: transparent; color: var(--bad); border: 1.5px solid var(--bad); margin-top: 20px; }
.btn:disabled { opacity: .45; }
.map { display: grid; grid-template-columns: 1fr 1fr 1fr; grid-template-rows: auto auto auto; gap: 8px; }
.map .truck { grid-column: 2; grid-row: 2; display: grid; place-items: center; color: var(--muted); padding: 4px; }
.map .truck :deep(svg) { width: 100%; max-width: 92px; height: auto; }
.slot { position: relative; aspect-ratio: 4/3; border: 1.5px dashed var(--line); border-radius: 12px; background: var(--slot); display: flex; flex-direction: column; align-items: center; justify-content: center; color: var(--muted); overflow: hidden; width: 100%; padding: 0; }
.slot.req { border-color: var(--accent); color: var(--ink); }
.slot.tall { aspect-ratio: auto; height: 100%; min-height: 120px; }
.slot.has { border: 0; }
.slot img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.slot .cap { position: relative; z-index: 1; background: linear-gradient(transparent, rgba(0,0,0,.72)); color: #fff; width: 100%; margin-top: auto; padding: 12px 6px 6px; font-size: .78rem; font-weight: 600; }
.pair { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.meter { display: grid; grid-template-columns: 42% 1fr; gap: 12px; align-items: center; }
.dmg { display: grid; grid-template-columns: 42% 1fr; gap: 12px; }
.doc { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 14px; }
.doc-h { display: flex; justify-content: space-between; gap: 8px; font-weight: 600; }
.seg { display: grid; grid-template-columns: repeat(3, 1fr); border: 1.5px solid var(--line); border-radius: 12px; overflow: hidden; margin-top: 10px; }
.seg.two { grid-template-columns: 1fr 1fr; }
.seg button { border: 0; background: transparent; min-height: 46px; color: inherit; }
.seg button + button { border-left: 1.5px solid var(--line); }
.seg button.on.y { background: var(--ok-soft); color: var(--ok); font-weight: 700; }
.seg button.on.n { background: var(--bad-soft); color: var(--bad); font-weight: 700; }
.seg button.on.x { background: rgba(59, 130, 246, 0.18); color: var(--accent); font-weight: 700; }
.add { display: flex; gap: 8px; }
.add .btn { width: auto; }
.rm { border: 0; background: transparent; color: var(--muted); text-decoration: underline; padding: 4px; }
.chk-note { margin-top: 10px; }
.issues { list-style: none; padding: 0; margin: 0; display: grid; gap: 6px; }
.issues li { padding: 10px 12px; border-radius: 12px; font-weight: 500; }
.issues li.bad { background: var(--bad-soft); color: var(--bad); }
.issues li.warn { background: var(--warn-soft); color: var(--warn); }
.issues li.ok { background: var(--ok-soft); color: var(--ok); }
.kv { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px 14px; margin: 0; }
.kv dt { color: var(--muted); }
.kv dd { margin: 0; font-weight: 600; text-align: right; }
.hero { padding: 18px; border-radius: 20px; background: var(--accent); color: var(--accent-ink); }
.delta { display: flex; gap: 18px; margin-top: 10px; }
.delta b { display: block; font-size: 1.1rem; }
.sigwrap { position: relative; background: #fff; border: 1.5px dashed var(--line); border-radius: 12px; overflow: hidden; }
#sig { display: block; width: 100%; height: 180px; touch-action: none; }
.sig-hint { position: absolute; left: 24px; right: 24px; bottom: 12px; text-align: center; color: #8A96A3; pointer-events: none; }
.sig-img { display: block; max-width: 100%; background: #fff; border-radius: 8px; }
.pill { display: inline-block; font-size: .78rem; font-weight: 600; padding: 3px 9px; border-radius: 999px; }
.pill.draft, .pill.closing, .pill.warn { background: var(--warn-soft); color: var(--warn); }
.pill.active { background: rgba(59, 130, 246, 0.18); color: var(--accent); }
.pill.closed, .pill.ok { background: var(--ok-soft); color: var(--ok); }
.pill.bad { background: var(--bad-soft); color: var(--bad); }
.bar { position: sticky; bottom: 0; background: var(--paper); border-top: 1px solid var(--line); padding: 10px 0 calc(10px + env(safe-area-inset-bottom, 0px)); }
.bar .in { display: flex; gap: 10px; }
.bar .btn.sec { flex: 0 0 34%; }
.hidden { display: none; }
.lb { position: fixed; inset: 0; z-index: 40; background: rgba(5, 8, 12, .94); display: flex; flex-direction: column; padding: 16px; gap: 10px; color: #fff; }
.lb img { flex: 1; min-height: 0; width: 100%; object-fit: contain; }
.lb .row, .mbox .row { display: flex; gap: 10px; }
.modal { justify-content: center; background: rgba(5, 8, 12, .6); }
.mbox { background: var(--card); color: var(--ink); border-radius: 18px; padding: 18px; max-width: 420px; width: 100%; margin: auto; }
.toast { position: fixed; left: 50%; bottom: calc(90px + env(safe-area-inset-bottom, 0px)); transform: translateX(-50%); background: var(--ink); color: var(--paper); padding: 10px 16px; border-radius: 12px; z-index: 50; }
.error { color: #fca5a5; }
.doc-photo { margin-top: 10px; width: 55%; }
.refuel { display: grid; gap: 6px; margin-bottom: 10px; }
.prev { display: grid; gap: 6px; }
</style>
