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
}>();

const emit = defineEmits<{
  back: [];
  refresh: [];
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
      <button class="ghost" type="button" :disabled="loading" @click="emit('refresh')">Обновить</button>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <section ref="listRef" class="list">
      <article v-for="m in items" :key="m.id" class="msg">
        <div class="meta">
          <strong>{{ m.author_name }}</strong>
          <span class="time">{{ new Date(m.created_at).toLocaleString() }}</span>
        </div>
        <p class="text">{{ m.text }}</p>
      </article>
      <p v-if="!items.length && !loading" class="empty">Сообщений пока нет.</p>
    </section>

    <footer class="composer">
      <textarea v-model="draft" rows="2" placeholder="Сообщение..." :disabled="!canSend" />
      <button class="primary" type="button" :disabled="!canSubmit" @click="submit">Отправить</button>
    </footer>
  </section>
</template>

<style scoped>
.chat-wrap {
  display: grid;
  gap: 0.75rem;
  min-height: calc(100vh - 6rem);
}
.head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.list {
  flex: 1;
  min-height: 0;
  max-height: calc(100vh - 15rem);
  overflow: auto;
  display: grid;
  gap: 0.55rem;
  border: 1px solid #243043;
  border-radius: 12px;
  background: rgba(2, 6, 23, 0.4);
  padding: 0.65rem;
}
.msg {
  border: 1px solid #334155;
  border-radius: 12px;
  background: #0b1220;
  padding: 0.55rem 0.7rem;
  display: grid;
  gap: 0.25rem;
}
.meta {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  align-items: baseline;
}
.time {
  color: #94a3b8;
  font-size: 0.8rem;
}
.text {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.composer {
  position: sticky;
  bottom: 0;
  display: grid;
  gap: 0.45rem;
  background: linear-gradient(180deg, transparent, #020617 35%);
  padding: 0.65rem 0 0;
}
textarea {
  width: 100%;
  border-radius: 10px;
  border: 1px solid #334155;
  background: #0b1220;
  color: #fff;
  padding: 0.55rem 0.65rem;
}
.primary {
  border: none;
  border-radius: 10px;
  background: #2563eb;
  color: #fff;
  padding: 0.55rem 0.8rem;
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
</style>

