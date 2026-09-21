<script setup lang="ts">
import { computed } from "vue";

import { connectionSnapshot } from "../connectionWatch";
import { clearDebugErrors, debugErrors, formatDebugDump, latestDebugError, markDebugErrorsRead } from "../debugLog";

const emit = defineEmits<{
  close: [];
}>();

const dumpText = computed(() => formatDebugDump(connectionSnapshot()));

const latest = computed(() => latestDebugError.value);

async function copyDump(): Promise<void> {
  try {
    await navigator.clipboard.writeText(dumpText.value);
  } catch {
    const area = document.createElement("textarea");
    area.value = dumpText.value;
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    document.body.removeChild(area);
  }
  markDebugErrorsRead();
}

function onClose(): void {
  markDebugErrorsRead();
  emit("close");
}
</script>

<template>
  <div class="overlay" @click.self="onClose">
    <article class="panel" role="dialog" aria-modal="true" aria-label="Отладка соединения">
      <header class="head">
        <h2>Отладка ошибок</h2>
        <button type="button" class="ghost" @click="onClose">Закрыть</button>
      </header>
      <p class="note">
        Временный разбор для администратора: снимок связи, очередь синка и последние сбои. Скопируйте текст и
        пришлите, если ошибка повторяется.
      </p>

      <section v-if="latest" class="latest">
        <h3>Последняя ошибка</h3>
        <p><strong>{{ latest.source }}</strong> · {{ latest.at }}</p>
        <p class="msg">{{ latest.message }}</p>
        <p v-if="latest.status != null">HTTP {{ latest.status }} {{ latest.method || "" }} {{ latest.url || "" }}</p>
        <p>online={{ latest.online }} · visibility={{ latest.visibility }} · net={{ latest.effectiveType || "—" }}</p>
      </section>

      <section>
        <h3>Снимок соединения</h3>
        <pre class="dump">{{ JSON.stringify(connectionSnapshot(), null, 2) }}</pre>
      </section>

      <section>
        <h3>Журнал ({{ debugErrors.length }})</h3>
        <ol v-if="debugErrors.length" class="log">
          <li v-for="item in debugErrors" :key="item.id">
            <div class="log-head">{{ item.at }} · {{ item.source }}</div>
            <div>{{ item.message }}</div>
            <div v-if="item.url" class="muted">{{ item.method }} {{ item.url }} {{ item.status != null ? `HTTP ${item.status}` : "" }}</div>
            <pre v-if="item.stack" class="stack">{{ item.stack }}</pre>
            <pre v-if="item.bodyPreview" class="stack">{{ item.bodyPreview }}</pre>
          </li>
        </ol>
        <p v-else class="muted">Ошибок пока нет. Журнал заполнится при сбое запроса, health-check или необработанном исключении.</p>
      </section>

      <div class="actions">
        <button type="button" class="primary" @click="copyDump">Скопировать всё</button>
        <button type="button" class="ghost" @click="clearDebugErrors">Очистить журнал</button>
      </div>
    </article>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 150;
  background: rgba(2, 6, 23, 0.78);
  display: grid;
  place-items: center;
  padding: 0.75rem;
}
.panel {
  width: min(720px, 100%);
  max-height: min(88dvh, 860px);
  overflow: auto;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: #0b1220;
  padding: 1rem;
  display: grid;
  gap: 0.75rem;
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
h2,
h3 {
  margin: 0;
}
h2 {
  font-size: 1.05rem;
}
h3 {
  font-size: 0.86rem;
  color: #93c5fd;
  margin-bottom: 0.3rem;
}
.note,
.muted {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.82rem;
  line-height: 1.4;
}
.msg {
  margin: 0.2rem 0;
  color: #fecaca;
  word-break: break-word;
}
.dump,
.stack {
  margin: 0;
  padding: 0.55rem;
  border-radius: 10px;
  background: #020617;
  border: 1px solid #1e293b;
  font-size: 0.72rem;
  line-height: 1.4;
  overflow: auto;
  max-height: 220px;
  white-space: pre-wrap;
  word-break: break-word;
}
.log {
  margin: 0;
  padding-left: 1.1rem;
  display: grid;
  gap: 0.55rem;
  font-size: 0.8rem;
}
.log-head {
  color: #93c5fd;
  font-size: 0.75rem;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}
.primary,
.ghost {
  min-height: 40px;
  border-radius: 10px;
  padding: 0.4rem 0.75rem;
}
.primary {
  border: none;
  background: #2563eb;
  color: #fff;
}
.ghost {
  border: 1px solid var(--border-strong);
  background: transparent;
  color: #cbd5e1;
}
</style>
