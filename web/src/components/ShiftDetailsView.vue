<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";

import { fetchShiftImageBlob } from "../api";
import {
  ALL_SLOTS,
  analyseShift,
  diffNum,
  ensurePhase,
  expStatus,
  fmtDT,
  fmtNum,
  fuelStats,
  slotLabel,
  workflowLabel,
  type ShiftCheck,
  type ShiftDoc,
  type ShiftPhase,
  type ShiftPhasePayload
} from "../shiftInspection";
import {
  dailyDateLabel,
  dailyItemLabel,
  dailyStatusLabel,
  dailyWhenLabel,
  type ShiftDailyCheck
} from "../shiftDaily";
import type { DriverShiftDetails, DriverShiftImageMeta } from "../types";

const props = defineProps<{
  shift: DriverShiftDetails | null;
  loading: boolean;
  error: string;
  authToken: string;
  canInspect?: boolean;
}>();

const emit = defineEmits<{
  back: [];
  openRoute: [routeId: string];
  openInspect: [];
}>();

const thumbs = ref<Record<number, string>>({});
const viewer = ref<{ id: number; url: string; title: string; kind: string; slot: string } | null>(null);
const busyId = ref<number | null>(null);
const tab = ref<ShiftPhase | "routes">("start");

const intake = computed(() => ensurePhase(props.shift?.intake || undefined));
const handover = computed(() => (props.shift?.handover ? ensurePhase(props.shift.handover) : null));
const photoKeysStart = computed(() => imagesFor("start").map((img) => img.slot).filter(Boolean));
const photoKeysEnd = computed(() => imagesFor("end").map((img) => img.slot).filter(Boolean));
const issuesStart = computed(() =>
  analyseShift({
    driver_name: props.shift?.driver_full_name || "",
    truck: props.shift?.truck || "",
    intake: intake.value,
    handover: handover.value,
    photoKeys: photoKeysStart.value,
    phase: "start"
  })
);
const issuesEnd = computed(() =>
  handover.value
    ? analyseShift({
        driver_name: props.shift?.driver_full_name || "",
        truck: props.shift?.truck || "",
        intake: intake.value,
        handover: handover.value,
        photoKeys: photoKeysEnd.value,
        phase: "end"
      })
    : []
);
const fuel = computed(() => fuelStats(intake.value, handover.value, props.shift?.refuels || []));
const title = computed(() => props.shift?.title || "Вахта");
const hasHandover = computed(() => Boolean(handover.value) || props.shift?.workflow_status === "closing" || props.shift?.workflow_status === "closed");
const dailyChecks = computed(() => props.shift?.daily_checks || []);

function dailyStatusClass(row: ShiftDailyCheck): string {
  if (row.status === "skipped") return "skipped";
  if (row.has_fault || (row.status === "done" && row.items.some((item) => item.st === "bad"))) return "bad";
  if (row.status === "done") return "ok";
  return "pending";
}

function imagesFor(phase: ShiftPhase): DriverShiftImageMeta[] {
  return (props.shift?.images || []).filter((item) => {
    const inferred = item.phase || (String(item.kind).startsWith("end") ? "end" : "start");
    return inferred === phase;
  });
}

function photoTitle(img: DriverShiftImageMeta): string {
  if (img.kind === "start_waybill") return "Путевой лист";
  return slotLabel(img.slot || img.kind);
}

function revokeThumbs(): void {
  Object.values(thumbs.value).forEach((url) => URL.revokeObjectURL(url));
  thumbs.value = {};
}

function closeViewer(): void {
  if (viewer.value?.url) URL.revokeObjectURL(viewer.value.url);
  viewer.value = null;
}

function fileName(kind: string, slot: string): string {
  return `${photoTitle({ id: 0, kind, slot, content_type: "" }).replace(/\s+/g, "_")}.jpg`;
}

async function openImage(id: number, kind: string, slot: string): Promise<void> {
  if (!props.authToken) return;
  busyId.value = id;
  try {
    const blob = await fetchShiftImageBlob(props.authToken, id, { thumbnail: false });
    closeViewer();
    viewer.value = { id, url: URL.createObjectURL(blob), title: photoTitle({ id, kind, slot, content_type: "" }), kind, slot };
  } catch {
    // ignore
  } finally {
    busyId.value = null;
  }
}

async function downloadImage(id: number, kind: string, slot: string): Promise<void> {
  if (!props.authToken) return;
  busyId.value = id;
  try {
    const blob = await fetchShiftImageBlob(props.authToken, id, { thumbnail: false });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName(kind, slot);
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
  } catch {
    // ignore
  } finally {
    busyId.value = null;
  }
}

function docLabel(doc: ShiftDoc): string {
  if (doc.has === "y") return "Есть";
  if (doc.has === "n") return "Нет";
  if (doc.has === "x") return "Не нужен";
  return "Не отмечено";
}

function checkLabel(item: ShiftCheck): string {
  if (item.st === "ok") return "Норма";
  if (item.st === "bad") return "Неисправно";
  return "Не проверено";
}

watch(
  () => `${props.shift?.id ?? ""}:${props.authToken}:${(props.shift?.images || []).map((img) => img.id).join(",")}`,
  async () => {
    revokeThumbs();
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

watch(
  () => props.shift?.id,
  () => {
    tab.value = "start";
  }
);

onUnmounted(() => {
  revokeThumbs();
  closeViewer();
});
</script>

<template>
  <section class="wrap">
    <button class="ghost" type="button" @click="emit('back')">← К списку вахт</button>
    <p v-if="loading && !shift">Загрузка…</p>
    <p v-if="error" class="error">{{ error }}</p>

    <article v-if="shift" class="head card">
      <div class="head-top">
        <h2>{{ title }}</h2>
        <span class="pill" :class="shift.workflow_status || shift.status">{{ workflowLabel(shift.workflow_status || shift.status) }}</span>
      </div>
      <dl class="kv">
        <dt>Водитель</dt><dd>{{ shift.driver_full_name || "—" }}</dd>
        <dt>Тягач</dt><dd class="plate">{{ shift.truck || "—" }}</dd>
        <dt>Прицеп</dt><dd class="plate">{{ shift.trailer || "—" }}</dd>
        <dt>Начало</dt><dd>{{ fmtDT(shift.started_at) }}</dd>
        <dt>Окончание</dt><dd>{{ shift.ended_at ? fmtDT(shift.ended_at) : "ещё идёт" }}</dd>
        <dt>Место</dt><dd>{{ shift.place || intake.place || "—" }}</dd>
      </dl>
      <div v-if="handover" class="delta">
        <div><b>{{ diffNum(intake.odo, handover.odo) == null ? "—" : fmtNum(diffNum(intake.odo, handover.odo)) + " км" }}</b><span>пробег</span></div>
        <div><b>{{ diffNum(intake.reefer, handover.reefer) == null ? "—" : fmtNum(diffNum(intake.reefer, handover.reefer)) }}</b><span>моточасы рефа</span></div>
        <div><b>{{ fuel.per100 == null ? "—" : fmtNum(fuel.per100) }}</b><span>л/100 км</span></div>
        <div><b>{{ fmtNum(fuel.refuel) }} л</b><span>заправлено</span></div>
      </div>
      <button v-if="canInspect" class="primary" type="button" @click="emit('openInspect')">Продолжить заполнение как водитель</button>
    </article>

    <article v-if="shift" class="card daily-history">
      <h3>Ежедневное ТО</h3>
      <p v-if="!dailyChecks.length" class="empty">Пока нет ежедневных проверок. Они появляются со следующего дня активной вахты.</p>
      <div v-for="row in dailyChecks" :key="row.id" class="daily-row">
        <div class="daily-head">
          <strong>{{ dailyDateLabel(row.check_date) }}</strong>
          <span class="pill" :class="dailyStatusClass(row)">{{ dailyStatusLabel(row.status) }}</span>
        </div>
        <p class="muted">{{ dailyWhenLabel(row) }}</p>
        <p v-if="row.status === 'skipped'" class="empty">Водитель пропустил проверку</p>
        <table v-else-if="row.status === 'done'" class="table">
          <tbody>
            <tr v-for="item in row.items" :key="item.key">
              <td>{{ item.name }}</td>
              <td :class="item.st === 'bad' ? 'bad' : ''">{{ dailyItemLabel(item) }}{{ item.note ? ` · ${item.note}` : "" }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="muted">Ожидает ответа водителя</p>
      </div>
    </article>

    <nav v-if="shift" class="tabs">
      <button type="button" :class="{ on: tab === 'start' }" @click="tab = 'start'">Приёмка</button>
      <button type="button" :class="{ on: tab === 'end' }" :disabled="!hasHandover" @click="tab = 'end'">Сдача</button>
      <button type="button" :class="{ on: tab === 'routes' }" @click="tab = 'routes'">Рейсы</button>
    </nav>

    <div v-if="shift" class="phases">
      <section v-show="tab === 'start'" class="phase card">
        <h3>Приёмка ТС</h3>
        <ul class="issues">
          <li v-if="!issuesStart.length" class="ok">Замечаний на приёмке нет</li>
          <li v-for="(item, idx) in issuesStart" :key="'s' + idx" :class="item[0]">{{ item[1] }}</li>
        </ul>
        <dl class="kv">
          <dt>Время</dt><dd>{{ fmtDT(intake.time || shift.started_at) }}</dd>
          <dt>Место</dt><dd>{{ intake.place || shift.place || "—" }}</dd>
          <dt>Одометр</dt><dd>{{ fmtNum(intake.odo) }} км</dd>
          <dt>Топливо</dt><dd>{{ fmtNum(intake.fuel) }} л</dd>
          <dt>Моточасы рефа</dt><dd>{{ fmtNum(intake.reefer) }}</dd>
        </dl>
        <h4>Фото</h4>
        <div class="photos">
          <button
            v-for="img in imagesFor('start')"
            :key="img.id"
            type="button"
            class="thumb"
            :disabled="busyId === img.id"
            @click="openImage(img.id, img.kind, img.slot)"
          >
            <img v-if="thumbs[img.id]" :src="thumbs[img.id]" :alt="photoTitle(img)" />
            <small>{{ photoTitle(img) }}</small>
          </button>
          <p v-if="!imagesFor('start').length" class="empty">Нет фото приёмки</p>
        </div>
        <p class="muted">Обязательные ракурсы: {{ ALL_SLOTS.filter((s) => s.req && photoKeysStart.includes(s.k)).length }} из {{ ALL_SLOTS.filter((s) => s.req).length }}</p>
        <h4>Документы</h4>
        <table class="table">
          <tbody>
            <tr v-for="doc in intake.docs" :key="doc.id">
              <td>{{ doc.name }}</td>
              <td :class="doc.has === 'n' ? 'bad' : ''">{{ docLabel(doc) }}</td>
              <td>{{ expStatus(doc)?.t || "—" }}</td>
            </tr>
          </tbody>
        </table>
        <h4>Состояние</h4>
        <table class="table">
          <tbody>
            <tr v-for="item in intake.checks" :key="item.id">
              <td>{{ item.name }}</td>
              <td :class="item.st === 'bad' ? 'bad' : ''">{{ checkLabel(item) }}{{ item.note ? ` · ${item.note}` : "" }}</td>
            </tr>
          </tbody>
        </table>
        <h4>Повреждения</h4>
        <p v-if="!intake.damages.length" class="empty">Не отмечены</p>
        <ul v-else class="plain">
          <li v-for="d in intake.damages" :key="d.id">{{ d.note || "без описания" }}</li>
        </ul>
      </section>

      <section v-if="hasHandover" v-show="tab === 'end'" class="phase card">
        <h3>Сдача ТС</h3>
        <p v-if="!handover" class="empty">Сдача ещё не начата</p>
        <template v-else>
          <ul class="issues">
            <li v-if="!issuesEnd.length" class="ok">Замечаний на сдаче нет</li>
            <li v-for="(item, idx) in issuesEnd" :key="'e' + idx" :class="item[0]">{{ item[1] }}</li>
          </ul>
          <dl class="kv">
            <dt>Время</dt><dd>{{ fmtDT(handover.time || shift.ended_at) }}</dd>
            <dt>Место</dt><dd>{{ handover.place || "—" }}</dd>
            <dt>Одометр</dt><dd>{{ fmtNum(handover.odo) }} км</dd>
            <dt>Топливо</dt><dd>{{ fmtNum(handover.fuel) }} л</dd>
            <dt>Моточасы рефа</dt><dd>{{ fmtNum(handover.reefer) }}</dd>
          </dl>
          <h4>Фото</h4>
          <div class="photos">
            <button
              v-for="img in imagesFor('end')"
              :key="img.id"
              type="button"
              class="thumb"
              :disabled="busyId === img.id"
              @click="openImage(img.id, img.kind, img.slot)"
            >
              <img v-if="thumbs[img.id]" :src="thumbs[img.id]" :alt="photoTitle(img)" />
              <small>{{ photoTitle(img) }}</small>
            </button>
            <p v-if="!imagesFor('end').length" class="empty">Нет фото сдачи</p>
          </div>
          <h4>Документы</h4>
          <table class="table">
            <tbody>
              <tr v-for="doc in handover.docs" :key="doc.id">
                <td>{{ doc.name }}</td>
                <td :class="doc.has === 'n' ? 'bad' : ''">{{ docLabel(doc) }}</td>
                <td>{{ expStatus(doc)?.t || "—" }}</td>
              </tr>
            </tbody>
          </table>
          <h4>Состояние</h4>
          <table class="table">
            <tbody>
              <tr v-for="item in handover.checks" :key="item.id">
                <td>{{ item.name }}</td>
                <td :class="item.st === 'bad' ? 'bad' : ''">{{ checkLabel(item) }}{{ item.note ? ` · ${item.note}` : "" }}</td>
              </tr>
            </tbody>
          </table>
          <h4>Повреждения</h4>
          <p v-if="!handover.damages.length" class="empty">Не отмечены</p>
          <ul v-else class="plain">
            <li v-for="d in handover.damages" :key="d.id">{{ d.note || "без описания" }}</li>
          </ul>
        </template>
      </section>
    </div>

    <article v-if="shift" v-show="tab === 'routes'" class="card routes-block">
      <h3>Рейсы за вахту</h3>
      <div class="routes">
        <button v-for="route in shift.routes" :key="route.id" class="route-card" type="button" @click="emit('openRoute', route.id)">
          <strong>#{{ route.id }}</strong>
          <small>ТС: {{ route.number_auto || "—" }} · точек: {{ route.points_count }}</small>
        </button>
        <p v-if="!shift.routes.length" class="empty">За эту вахту рейсов нет</p>
      </div>
      <template v-if="(shift.refuels || []).length">
        <h3>Заправки</h3>
        <table class="table">
          <tbody>
            <tr v-for="item in shift.refuels" :key="item.id">
              <td>{{ fmtDT(item.time) }}</td>
              <td>{{ item.liters || "—" }} л</td>
              <td>{{ item.odo || "—" }} км</td>
              <td>{{ item.place || "—" }}</td>
            </tr>
          </tbody>
        </table>
      </template>
    </article>

    <div v-if="viewer" class="lightbox" @click.self="closeViewer">
      <article class="lightbox-card">
        <h3>{{ viewer.title }}</h3>
        <img :src="viewer.url" :alt="viewer.title" />
        <div class="lightbox-actions">
          <button type="button" class="ghost" @click="downloadImage(viewer.id, viewer.kind, viewer.slot)">Скачать</button>
          <button type="button" class="ghost" @click="closeViewer">Закрыть</button>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.wrap {
  display: grid;
  gap: 0.85rem;
  width: 100%;
  max-width: 1120px;
  margin: 0 auto;
}
.card {
  display: grid;
  gap: 0.7rem;
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: rgba(17, 24, 39, 0.88);
  min-width: 0;
}
.head-top { display: flex; justify-content: space-between; gap: 0.75rem; align-items: flex-start; }
h2, h3, h4 { margin: 0; }
h3 { font-size: 1.05rem; }
h4 { font-size: 0.82rem; letter-spacing: 0.04em; text-transform: uppercase; color: var(--text-muted); margin-top: 0.4rem; }
.primary {
  min-height: 44px;
  width: auto;
  justify-self: start;
  border: none;
  border-radius: 12px;
  background: var(--primary-strong, #2563eb);
  color: #fff;
  font-weight: 700;
  padding: 0 1rem;
}
.kv { display: grid; grid-template-columns: 9.5rem minmax(0, 1fr); gap: 0.35rem 0.8rem; margin: 0; }
.kv dt { color: var(--text-muted); }
.kv dd { margin: 0; font-weight: 600; overflow-wrap: anywhere; }
.plate { letter-spacing: 0.04em; }
.delta { display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 0.6rem; padding: 0.8rem; border-radius: 14px; background: rgba(37, 99, 235, 0.18); }
.delta b { display: block; font-size: 1.05rem; }
.delta span { color: var(--text-muted); font-size: 0.8rem; }
.tabs { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 4px; background: var(--surface, #111827); border: 1px solid var(--border); border-radius: 12px; padding: 3px; }
.tabs button { border: 0; background: transparent; min-height: 40px; border-radius: 9px; color: var(--text-muted); font-weight: 600; }
.tabs button.on { background: var(--primary, #2563eb); color: #fff; }
.phases { display: grid; gap: 0.85rem; }
@media (min-width: 960px) {
  .phases { grid-template-columns: 1fr 1fr; align-items: start; }
  .tabs { display: none; }
  .phase, .routes-block { display: grid !important; }
}
.photos { display: grid; grid-template-columns: repeat(auto-fill, minmax(104px, 1fr)); gap: 0.45rem; }
.thumb { padding: 0; border: none; background: transparent; color: inherit; display: grid; gap: 0.2rem; min-width: 0; }
.thumb img { width: 100%; height: 88px; object-fit: cover; border-radius: 10px; border: 1px solid var(--border); display: block; }
.thumb small { font-size: 0.72rem; color: var(--text-muted); line-height: 1.2; }
.table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
.table td { padding: 0.35rem 0.4rem; border-bottom: 1px solid var(--border); vertical-align: top; }
.table td:first-child { color: var(--text-muted); width: 52%; }
.issues { list-style: none; padding: 0; margin: 0; display: grid; gap: 4px; }
.issues li { padding: 8px 10px; border-radius: 10px; font-size: 0.88rem; }
.issues li.bad, .bad { color: #fca5a5; }
.issues li.bad { background: rgba(239, 68, 68, 0.16); }
.issues li.warn { background: rgba(245, 158, 11, 0.16); color: #fcd34d; }
.issues li.ok { background: rgba(34, 197, 94, 0.16); color: #86efac; }
.plain { margin: 0; padding-left: 1.1rem; }
.pill { display: inline-block; font-size: 0.78rem; font-weight: 600; padding: 3px 9px; border-radius: 999px; }
.pill.draft, .pill.closing { background: rgba(245, 158, 11, 0.16); color: #fbbf24; }
.pill.active { background: rgba(59, 130, 246, 0.18); color: #93c5fd; }
.pill.closed, .pill.ended, .pill.ok { background: rgba(34, 197, 94, 0.16); color: #86efac; }
.pill.skipped { background: rgba(148, 163, 184, 0.18); color: #cbd5e1; }
.pill.pending { background: rgba(245, 158, 11, 0.16); color: #fbbf24; }
.daily-history { gap: 0.85rem; }
.daily-row { display: grid; gap: 0.35rem; padding-bottom: 0.7rem; border-bottom: 1px solid var(--border); }
.daily-row:last-child { border-bottom: 0; padding-bottom: 0; }
.daily-head { display: flex; justify-content: space-between; gap: 0.5rem; align-items: center; }
.routes { display: grid; gap: 0.45rem; }
.route-card { text-align: left; border: 1px solid var(--border); border-radius: 12px; background: var(--surface-2, #111827); color: #fff; padding: 0.7rem; display: grid; gap: 0.2rem; }
.empty, .muted, .error { margin: 0; }
.muted { color: var(--text-muted); font-size: 0.82rem; }
.error { color: #fca5a5; }
.ghost { width: auto; justify-self: start; background: transparent; color: #bfdbfe; border: 1px solid var(--border-strong); border-radius: 10px; padding: 0.4rem 0.7rem; }
.lightbox { position: fixed; inset: 0; z-index: 80; background: rgba(2, 6, 23, 0.78); display: grid; place-items: center; padding: 1rem; }
.lightbox-card { width: min(720px, 100%); display: grid; gap: 0.65rem; padding: 0.9rem; border-radius: 16px; border: 1px solid var(--border); background: #0f172a; }
.lightbox-card img { width: 100%; max-height: 70vh; object-fit: contain; border-radius: 10px; }
.lightbox-actions { display: flex; justify-content: flex-end; gap: 0.5rem; }
</style>
