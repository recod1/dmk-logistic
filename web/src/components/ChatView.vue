<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";

export type ChatMessage = {
  id: number;
  route_id: string;
  user_id: number;
  author_name: string;
  text: string;
  created_at: string;
};

const props = defineProps<{
  routeId: string;
  items: ChatMessage[];
  loading: boolean;
  error: string;
  canSend: boolean;
  currentUserId?: number | null;
}>();

const emit = defineEmits<{
  back: [];
  send: [text: string];
}>();

const draft = ref("");
const listRef = ref<HTMLElement | null>(null);
const listInnerRef = ref<HTMLElement | null>(null);
let resizeObserver: ResizeObserver | null = null;

const canSubmit = computed(() => props.canSend && draft.value.trim().length > 0 && !props.loading);

function submit(): void {
  const text = draft.value.trim();
  if (!text) return;
  emit("send", text);
  draft.value = "";
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
}

watch(
  () => props.items,
  () => {
    void scrollToBottom();
  },
  { deep: true }
);

watch(
  () => props.loading,
  (v) => {
    if (!v) void scrollToBottom();
  }
);

watch(
  () => props.routeId,
  () => {
    void scrollToBottom();
  }
);

onMounted(() => {
  void scrollToBottom();
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
  resizeObserver?.disconnect();
  resizeObserver = null;
});
</script>

<template>
  <section class="chat-wrap">
    <header class="head-row">
      <button class="ghost" type="button" @click="emit('back')">← Назад</button>
      <h1 class="title">Чат рейса <span class="route-id">{{ routeId }}</span></h1>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <div ref="listRef" class="list" role="log" aria-live="polite">
      <div ref="listInnerRef" class="list-inner">
        <article
          v-for="m in items"
          :key="m.id"
          class="msg"
          :class="{ mine: Boolean(currentUserId) && m.user_id === currentUserId }"
        >
          <div class="bubble">
            <strong v-if="!currentUserId || m.user_id !== currentUserId" class="author">{{ m.author_name }}</strong>
            <p class="text">{{ m.text }}</p>
            <div class="bubble-foot">
              <span class="time">{{ new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) }}</span>
            </div>
          </div>
        </article>
        <p v-if="!items.length && !loading" class="empty">Сообщений пока нет.</p>
      </div>
    </div>

    <footer class="composer">
      <div class="composer-field">
        <textarea
          v-model="draft"
          rows="1"
          placeholder="Сообщение"
          :disabled="!canSend"
          @keydown.enter.exact.prevent="submit"
        />
      </div>
      <button class="send-btn" type="button" :disabled="!canSubmit" title="Отправить" @click="submit">➤</button>
    </footer>
  </section>
</template>

<style scoped>
/* Визуально ближе к Telegram (тёмная тема): фон чата, «хвостатые» пузыри, ширина ~75%. */
.chat-wrap {
  flex: 1;
  min-height: 0;
  width: 100%;
  max-width: 720px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  background: #0e1621;
  color: #e7edf4;
}

.head-row {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.65rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  background: #17212b;
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

.route-id {
  font-weight: 700;
  color: #8eb2ea;
}

.list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
}

.list-inner {
  box-sizing: border-box;
  min-height: 100%;
  padding: 0.5rem 0.65rem 0.75rem;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
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
  border-radius: 12px 12px 12px 4px;
  padding: 0.35rem 0.55rem 0.28rem;
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
  margin-top: 0.12rem;
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

.composer {
  flex-shrink: 0;
  display: flex;
  align-items: flex-end;
  gap: 0.45rem;
  padding: 0.5rem 0.65rem calc(0.55rem + env(safe-area-inset-bottom, 0));
  background: #17212b;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.composer-field {
  flex: 1;
  min-width: 0;
  border-radius: 22px;
  background: #0e1621;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.composer textarea {
  display: block;
  width: 100%;
  min-height: 40px;
  max-height: 32vh;
  border: none;
  border-radius: 22px;
  background: transparent;
  color: #e7edf4;
  padding: 0.55rem 0.85rem;
  resize: none;
  overflow-y: auto;
  line-height: 1.35;
  font-size: 0.95rem;
  font-family: inherit;
}

.composer textarea:focus {
  outline: none;
}

.composer textarea::placeholder {
  color: rgba(255, 255, 255, 0.35);
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
}

.send-btn:disabled {
  opacity: 0.38;
  cursor: not-allowed;
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
</style>
