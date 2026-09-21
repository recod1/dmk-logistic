<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";

export type ChatMessage = {
  id: number;
  route_id: string;
  user_id: number;
  author_name: string;
  text: string;
  created_at: string;
  read?: boolean;
  attachments?: Array<{ id: number; original_name: string; content_type: string; file_size: number }>;
};

const props = defineProps<{
  routeId: string;
  title?: string;
  items: ChatMessage[];
  loading: boolean;
  error: string;
  canSend: boolean;
  currentUserId?: number | null;
}>();

const emit = defineEmits<{
  back: [];
  send: [text: string];
  upload: [payload: { text: string; files: File[] }];
  download: [payload: { attachmentId: number; originalName: string }];
}>();

const draft = ref("");
const fileInputRef = ref<HTMLInputElement | null>(null);
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const pickedFiles = ref<File[]>([]);
const listRef = ref<HTMLElement | null>(null);
const listInnerRef = ref<HTMLElement | null>(null);
let resizeObserver: ResizeObserver | null = null;
const stickToBottom = ref(true);
const showJump = ref(false);
const emojiOpen = ref(false);
const EMOJIS = [
  "👍",
  "👎",
  "✅",
  "❌",
  "⚠️",
  "🚚",
  "📍",
  "📞",
  "⏱️",
  "🧾",
  "📸",
  "🗺️",
  "😊",
  "😂",
  "🙏",
  "🔥",
  "💪",
  "💬",
  "❗",
  "❓"
] as const;

const canSubmit = computed(() => props.canSend && draft.value.trim().length > 0 && !props.loading);

function isMine(message: ChatMessage): boolean {
  return Boolean(props.currentUserId) && message.user_id === props.currentUserId;
}

const COMPOSER_LINE_PX = 40;
const COMPOSER_MAX_PX = 120;

function autosizeComposer(): void {
  const el = textareaRef.value;
  if (!el) {
    return;
  }
  if (!draft.value) {
    el.style.height = `${COMPOSER_LINE_PX}px`;
    el.style.overflowY = "hidden";
    return;
  }
  el.style.overflowY = "hidden";
  el.style.height = `${COMPOSER_LINE_PX}px`;
  const needed = el.scrollHeight;
  const next = Math.min(Math.max(needed, COMPOSER_LINE_PX), COMPOSER_MAX_PX);
  el.style.height = `${next}px`;
  el.style.overflowY = needed > COMPOSER_MAX_PX ? "auto" : "hidden";
}

function onTextareaTouchMove(event: TouchEvent): void {
  const el = textareaRef.value;
  if (!el || el.scrollHeight <= el.clientHeight + 1) {
    event.preventDefault();
  }
}

function bindTextareaTouch(): void {
  textareaRef.value?.addEventListener("touchmove", onTextareaTouchMove, { passive: false });
}

function unbindTextareaTouch(): void {
  textareaRef.value?.removeEventListener("touchmove", onTextareaTouchMove);
}

function submit(): void {
  const text = draft.value.trim();
  if (!text) return;
  emit("send", text);
  draft.value = "";
  void nextTick(() => autosizeComposer());
}

function triggerPickFiles(): void {
  fileInputRef.value?.click();
}

function addPickedFiles(files: File[]): void {
  if (!files.length || !props.canSend || props.loading) {
    return;
  }
  pickedFiles.value = [...pickedFiles.value, ...files];
}

function filesFromClipboard(data: DataTransfer | null): File[] {
  if (!data) {
    return [];
  }
  const files: File[] = [];
  const seen = new Set<File>();
  for (const item of Array.from(data.items || [])) {
    if (item.kind === "file" && item.type.startsWith("image/")) {
      const file = item.getAsFile();
      if (file && !seen.has(file)) {
        seen.add(file);
        files.push(file);
      }
    }
  }
  for (const file of Array.from(data.files || [])) {
    if (file.type.startsWith("image/") && !seen.has(file)) {
      seen.add(file);
      files.push(file);
    }
  }
  return files;
}

function onPaste(ev: ClipboardEvent): void {
  const files = filesFromClipboard(ev.clipboardData);
  if (!files.length) {
    return;
  }
  ev.preventDefault();
  addPickedFiles(files);
}

function onPickFiles(ev: Event): void {
  const input = ev.target as HTMLInputElement;
  const list = input.files ? Array.from(input.files) : [];
  if (list.length) {
    addPickedFiles(list);
  }
  input.value = "";
}

function submitFiles(): void {
  if (!props.canSend || props.loading) {
    return;
  }
  const files = pickedFiles.value;
  if (!files.length) return;
  emit("upload", { text: draft.value.trim(), files });
  pickedFiles.value = [];
  draft.value = "";
  if (fileInputRef.value) {
    fileInputRef.value.value = "";
  }
  void nextTick(() => autosizeComposer());
}

function toggleEmoji(): void {
  emojiOpen.value = !emojiOpen.value;
}

function pickEmoji(emoji: string): void {
  if (!props.canSend || props.loading) {
    return;
  }
  const trimmed = draft.value.trim();
  if (!trimmed) {
    emit("send", emoji);
    draft.value = "";
    emojiOpen.value = false;
    return;
  }
  draft.value = `${draft.value}${emoji}`;
}

async function scrollToBottom(): Promise<void> {
  await nextTick();
  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => resolve());
    });
  });
  const el = listRef.value;
  if (!el) return;
  el.scrollTop = el.scrollHeight;
  stickToBottom.value = true;
  showJump.value = false;
}

function updateStickiness(): void {
  const el = listRef.value;
  if (!el) return;
  const threshold = 40;
  const dist = el.scrollHeight - (el.scrollTop + el.clientHeight);
  stickToBottom.value = dist <= threshold;
  showJump.value = !stickToBottom.value;
}

watch(
  () => props.items,
  () => {
    if (stickToBottom.value) {
      void scrollToBottom();
    } else {
      showJump.value = true;
    }
  },
  { deep: true }
);

watch(
  () => props.loading,
  (v) => {
    if (!v && stickToBottom.value) void scrollToBottom();
  }
);

watch(
  () => props.routeId,
  () => {
    stickToBottom.value = true;
    showJump.value = false;
    void scrollToBottom();
  }
);

watch(
  () => props.routeId,
  () => {
    emojiOpen.value = false;
  }
);

watch(draft, () => {
  void nextTick(() => autosizeComposer());
});

onMounted(() => {
  void scrollToBottom();
  autosizeComposer();
  bindTextareaTouch();
  window.addEventListener("paste", onPaste);
});

watch(
  () => listInnerRef.value,
  (inner) => {
    resizeObserver?.disconnect();
    resizeObserver = null;
    if (!inner || typeof ResizeObserver === "undefined") {
      return;
    }
    resizeObserver = new ResizeObserver(() => {
      void scrollToBottom();
    });
    resizeObserver.observe(inner);
  },
  { flush: "post" }
);

onUnmounted(() => {
  unbindTextareaTouch();
  window.removeEventListener("paste", onPaste);
  resizeObserver?.disconnect();
  resizeObserver = null;
});
</script>

<template>
  <section class="chat-wrap">
    <div class="chrome-top">
      <header class="head-row">
        <button class="ghost" type="button" @click="emit('back')">← Назад</button>
        <h1 class="title">
          <span class="title-prefix">{{ props.title ? "Чат" : "Чат рейса" }}</span>
          <span class="route-id">{{ props.title || routeId }}</span>
        </h1>
      </header>
      <p v-if="error" class="error">{{ error }}</p>
    </div>

    <div ref="listRef" class="list" role="log" aria-live="polite" @scroll.passive="updateStickiness">
      <button v-if="showJump" class="jump" type="button" @click="scrollToBottom">Новые сообщения ↓</button>
      <div ref="listInnerRef" class="list-inner">
        <article
          v-for="m in items"
          :key="m.id"
          class="msg"
          :class="{ mine: isMine(m) }"
        >
          <div class="bubble">
            <strong v-if="!currentUserId || m.user_id !== currentUserId" class="author">{{ m.author_name }}</strong>
            <p class="text">{{ m.text }}</p>
            <div v-if="m.attachments?.length" class="att">
              <button
                v-for="a in m.attachments"
                :key="a.id"
                type="button"
                class="att-btn"
                @click="emit('download', { attachmentId: a.id, originalName: a.original_name })"
              >
                📎 {{ a.original_name || `file-${a.id}` }}
              </button>
            </div>
            <div class="bubble-foot">
              <span class="time">{{ new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) }}</span>
              <span v-if="isMine(m)" class="ticks" :class="{ read: Boolean(m.read) }" :title="m.read ? 'Прочитано' : 'Отправлено'">
                <svg viewBox="0 0 12 10" aria-hidden="true">
                  <path d="M1.2 5.2 4.1 8.1 10.6 1.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
                <svg v-if="m.read" class="tick-2" viewBox="0 0 12 10" aria-hidden="true">
                  <path d="M1.2 5.2 4.1 8.1 10.6 1.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
              </span>
            </div>
          </div>
        </article>
        <p v-if="!items.length && !loading" class="empty">Сообщений пока нет.</p>
      </div>
    </div>

    <footer class="composer">
      <input ref="fileInputRef" type="file" multiple class="hidden-file" @change="onPickFiles" />
      <p v-if="pickedFiles.length" class="picked-hint">К отправке: {{ pickedFiles.length }} фото. Можно вставить ещё из буфера.</p>
      <div v-if="emojiOpen" class="emoji-panel" role="list">
        <button
          v-for="e in EMOJIS"
          :key="e"
          class="emoji-btn"
          type="button"
          :disabled="!canSend"
          @click="pickEmoji(e)"
        >
          {{ e }}
        </button>
      </div>
      <div class="composer-field">
        <textarea
          ref="textareaRef"
          v-model="draft"
          rows="1"
          placeholder="Сообщение или вставьте фото"
          :disabled="!canSend"
          @keydown.enter.exact.prevent="submit"
        />
      </div>
      <button class="emoji-toggle" type="button" :disabled="!canSend" title="Файлы" @click="triggerPickFiles">📎</button>
      <button class="emoji-toggle" type="button" :disabled="!canSend" title="Эмодзи" @click="toggleEmoji">🙂</button>
      <button v-if="pickedFiles.length" class="send-btn" type="button" :disabled="!canSend || loading" title="Отправить файлы" @click="submitFiles">
        ⤒
      </button>
      <button v-else class="send-btn" type="button" :disabled="!canSubmit" title="Отправить" @click="submit">➤</button>
    </footer>
  </section>
</template>

<style scoped>
.chat-wrap {
  flex: 1;
  min-height: 0;
  height: 100%;
  max-height: 100%;
  width: 100%;
  margin: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  overflow: hidden;
  overscroll-behavior: none;
  background: #0e1621;
  color: #e7edf4;
}

.chrome-top {
  grid-row: 1;
  min-width: 0;
  background: #17212b;
  z-index: 2;
}

.head-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.65rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.title {
  margin: 0;
  flex: 1;
  min-width: 0;
  font-size: 0.95rem;
  font-weight: 600;
  line-height: 1.25;
  text-align: center;
}

.title-prefix {
  margin-right: 0.35rem;
  color: rgba(255, 255, 255, 0.65);
  font-weight: 600;
}

.route-id {
  font-weight: 700;
  color: #8eb2ea;
}

.list {
  grid-row: 2;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
  touch-action: pan-y;
  position: relative;
}

.list-inner {
  box-sizing: border-box;
  padding: 0.5rem 0.65rem 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.msg {
  display: flex;
  width: 100%;
}

.msg:not(.mine) {
  justify-content: flex-start;
}

.msg.mine {
  justify-content: flex-end;
}

.bubble {
  max-width: min(340px, 78vw);
  border-radius: 14px 14px 14px 5px;
  padding: 0.4rem 0.6rem 0.32rem;
  background: #182533;
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.2);
}

.msg.mine .bubble {
  border-radius: 12px 12px 4px 12px;
  background: #2b5278;
}

.author {
  display: block;
  font-size: 0.78rem;
  font-weight: 600;
  color: #6ab3f7;
  margin-bottom: 0.12rem;
  line-height: 1.2;
}

.text {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 0.9375rem;
  line-height: 1.38;
  color: #e7edf4;
}

.bubble-foot {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 0.2rem;
  margin-top: 0.12rem;
}

.att {
  display: grid;
  gap: 0.25rem;
  margin-top: 0.35rem;
}
.att-btn {
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.06);
  color: #e7edf4;
  padding: 0.3rem 0.45rem;
  text-align: left;
  font: inherit;
}

.time {
  font-size: 0.68rem;
  line-height: 1;
  color: rgba(255, 255, 255, 0.45);
  user-select: none;
}

.msg.mine .time {
  color: rgba(255, 255, 255, 0.55);
}

.ticks {
  display: inline-flex;
  align-items: center;
  color: rgba(255, 255, 255, 0.5);
  line-height: 0;
}
.ticks svg {
  width: 14px;
  height: 10px;
  display: block;
}
.ticks .tick-2 {
  margin-left: -7px;
}
.ticks.read {
  color: #7ec8f5;
}

.composer {
  grid-row: 3;
  flex-shrink: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 0.45rem;
  padding: 0.5rem 0.65rem 0.55rem;
  background: #17212b;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  overflow: hidden;
  z-index: 2;
}
.picked-hint {
  flex: 1 0 100%;
  margin: 0;
  color: #93c5fd;
  font-size: 0.78rem;
}
.hidden-file {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}

.emoji-panel {
  width: 100%;
  display: grid;
  grid-template-columns: repeat(10, minmax(0, 1fr));
  gap: 0.25rem;
  padding: 0.35rem 0;
}

.emoji-btn {
  border: none;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.06);
  color: #fff;
  font-size: 1.15rem;
  line-height: 1;
  padding: 0.35rem 0;
}

.emoji-btn:disabled {
  opacity: 0.5;
}

.composer-field {
  flex: 1;
  min-width: 0;
  height: auto;
  border-radius: 22px;
  background: #0e1621;
  border: 1px solid rgba(255, 255, 255, 0.08);
  overflow: hidden;
}

.emoji-toggle {
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: none;
  background: rgba(255, 255, 255, 0.06);
  color: #fff;
  font-size: 1.1rem;
  line-height: 1;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: none;
}

.emoji-toggle:disabled {
  opacity: 0.38;
  cursor: not-allowed;
}

.composer textarea {
  display: block;
  width: 100%;
  height: 40px;
  min-height: 40px;
  max-height: 120px;
  border: none;
  border-radius: 22px;
  background: transparent;
  color: #e7edf4;
  padding: 0.55rem 0.85rem;
  resize: none;
  overflow: hidden;
  overflow-x: hidden;
  overflow-y: hidden;
  overscroll-behavior: none;
  line-height: 1.25;
  font-size: 16px;
  font-family: inherit;
  touch-action: manipulation;
}

.composer textarea:focus {
  outline: none;
}

.composer textarea::placeholder {
  color: rgba(255, 255, 255, 0.35);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.send-btn {
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: none;
  background: #5288c1;
  color: #fff;
  font-size: 1.1rem;
  line-height: 1;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: none;
}

.send-btn:disabled {
  opacity: 0.38;
  cursor: not-allowed;
}

@media (max-width: 420px) {
  .emoji-panel {
    grid-template-columns: repeat(8, minmax(0, 1fr));
  }
}

.ghost {
  flex-shrink: 0;
  border: none;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.06);
  color: #8eb2ea;
  padding: 0.42rem 0.55rem;
  font-size: 0.88rem;
}

.error {
  flex-shrink: 0;
  color: #fca5a5;
  margin: 0;
  padding: 0.35rem 0.65rem;
  font-size: 0.85rem;
  background: rgba(127, 29, 29, 0.25);
}

.empty {
  margin: 0;
  padding: 1rem 0;
  text-align: center;
  color: rgba(255, 255, 255, 0.38);
  font-size: 0.9rem;
}

.jump {
  position: sticky;
  bottom: 0.5rem;
  left: 50%;
  transform: translateX(-50%);
  z-index: 2;
  border: none;
  border-radius: 999px;
  background: rgba(34, 197, 94, 0.9);
  color: #052e16;
  padding: 0.35rem 0.65rem;
  font-size: 0.85rem;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.35);
}
</style>
