<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

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

const canSubmit = computed(() => props.canSend && draft.value.trim().length > 0 && !props.loading);

function submit(): void {
  const text = draft.value.trim();
  if (!text) return;
  emit("send", text);
  draft.value = "";
}

async function scrollToBottom(): Promise<void> {
  await nextTick();
  const el = listRef.value;
  if (!el) return;
  el.scrollTop = el.scrollHeight;
}

watch(
  () => props.items.length,
  () => {
    void scrollToBottom();
  }
);
</script>

<template>
  <section class="chat-wrap">
    <header class="head-row">
      <button class="ghost" type="button" @click="emit('back')">← Назад</button>
      <h1>Чат рейса {{ routeId }}</h1>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <section ref="listRef" class="list">
      <article
        v-for="m in items"
        :key="m.id"
        class="msg"
        :class="{ mine: Boolean(currentUserId) && m.user_id === currentUserId }"
      >
        <div class="bubble">
          <div class="meta">
            <strong class="author">{{ m.author_name }}</strong>
            <span class="time">{{ new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}</span>
          </div>
          <p class="text">{{ m.text }}</p>
        </div>
      </article>
      <p v-if="!items.length && !loading" class="empty">Сообщений пока нет.</p>
    </section>

    <footer class="composer">
      <textarea
        v-model="draft"
        rows="1"
        placeholder="Сообщение…"
        :disabled="!canSend"
        @keydown.enter.exact.prevent="submit"
      />
      <button class="primary" type="button" :disabled="!canSubmit" @click="submit">Отправить</button>
    </footer>
  </section>
</template>

<style scoped>
.chat-wrap {
  display: grid;
  gap: 0.55rem;
  min-height: calc(100vh - 6rem);
  width: 100%;
  padding: 0 0.25rem;
}
.head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.head-row h1 {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
}
.list {
  flex: 1;
  min-height: 0;
  max-height: calc(100vh - 14rem);
  overflow: auto;
  display: grid;
  gap: 0.35rem;
  border: none;
  border-radius: 0;
  background: transparent;
  padding: 0.35rem 0;
}
.msg {
  display: flex;
}
.msg.mine {
  justify-content: flex-end;
}
.bubble {
  max-width: min(540px, 92%);
  border: none;
  border-radius: 14px;
  background: #0f172a;
  padding: 0.45rem 0.65rem;
}
.msg.mine .bubble {
  background: #2563eb;
}
.meta {
  display: flex;
  gap: 0.45rem;
  align-items: baseline;
  justify-content: space-between;
}
.author {
  font-weight: 650;
  font-size: 0.82rem;
  color: #c7d2fe;
}
.msg.mine .author {
  display: none;
}
.time {
  color: rgba(255, 255, 255, 0.75);
  font-size: 0.78rem;
  white-space: nowrap;
}
.msg.mine .time {
  color: rgba(255, 255, 255, 0.85);
}
.text {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 0.95rem;
  line-height: 1.32;
  color: #f8fafc;
}
.msg.mine .text {
  color: #fff;
}
.composer {
  position: sticky;
  bottom: 0;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.45rem;
  align-items: end;
  background: #020617;
  padding: 0.55rem 0;
  border-top: 1px solid #111827;
}
textarea {
  width: 100%;
  min-height: 40px;
  border-radius: 12px;
  border: 1px solid #334155;
  background: #0b1220;
  color: #fff;
  padding: 0.45rem 0.6rem;
  resize: none;
  max-height: 34vh;
  overflow: auto;
  line-height: 1.25;
}
.primary {
  border: none;
  border-radius: 12px;
  background: #2563eb;
  color: #fff;
  padding: 0.45rem 0.75rem;
  height: 40px;
}
.ghost {
  width: auto;
  border: 1px solid #334155;
  border-radius: 10px;
  background: transparent;
  color: #bfdbfe;
  padding: 0.4rem 0.6rem;
}
.error {
  color: #fca5a5;
  margin: 0;
}
.empty {
  margin: 0;
  color: #94a3b8;
}

@media (min-width: 900px) {
  .chat-wrap {
    max-width: 780px;
    margin: 0 auto;
    padding: 0;
  }
}
</style>

