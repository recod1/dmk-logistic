<script setup lang="ts">
import { computed, ref, watch } from "vue";

export type LogisticsContactFormItem = { name: string; phone: string };

const props = defineProps<{
  items: LogisticsContactFormItem[];
  loading: boolean;
  saving: boolean;
  error: string;
}>();

const emit = defineEmits<{
  save: [items: LogisticsContactFormItem[]];
  refresh: [];
}>();

const localItems = ref<LogisticsContactFormItem[]>([]);

watch(
  () => props.items,
  (value) => {
    localItems.value = value.map((item) => ({ name: item.name, phone: item.phone }));
  },
  { immediate: true, deep: true }
);

const canSave = computed(() => !props.loading && !props.saving);

function addRow(): void {
  localItems.value.push({ name: "", phone: "" });
}

function removeRow(index: number): void {
  localItems.value.splice(index, 1);
}

function submit(): void {
  emit(
    "save",
    localItems.value.map((item) => ({ name: item.name.trim(), phone: item.phone.trim() })).filter((item) => item.name && item.phone)
  );
}
</script>

<template>
  <section class="wrap">
    <p v-if="error" class="error">{{ error }}</p>
    <div class="card">
      <div class="card-head">
        <h2>Контакты логистов</h2>
        <button type="button" class="ghost" :disabled="loading" @click="emit('refresh')">Обновить</button>
      </div>
      <p class="hint">
        Эти контакты показываются водителям в карточке рейса. Можно менять имена, телефоны и количество строк. Изменения
        применяются только к новым рейсам — уже созданные рейсы сохраняют прежний список контактов.
      </p>
      <div v-if="!localItems.length" class="empty">Контактов нет. Добавьте хотя бы одну строку или оставьте список пустым.</div>
      <div v-for="(item, index) in localItems" :key="index" class="row">
        <label class="field">
          Имя
          <input v-model="item.name" placeholder="Имя" />
        </label>
        <label class="field">
          Телефон
          <input v-model="item.phone" placeholder="+7 (900) 000-00-00" inputmode="tel" />
        </label>
        <button type="button" class="danger" :disabled="!canSave" @click="removeRow(index)">Удалить</button>
      </div>
      <div class="actions">
        <button type="button" class="secondary" :disabled="!canSave" @click="addRow">Добавить контакт</button>
        <button type="button" class="primary" :disabled="!canSave" @click="submit">Сохранить</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.wrap {
  width: 100%;
  max-width: 720px;
  margin: 0 auto;
  display: grid;
  gap: 0.75rem;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  flex-wrap: wrap;
}
h2 {
  margin: 0;
  font-size: 1.02rem;
}
.hint {
  margin: 0;
  color: #94a3b8;
  font-size: 0.88rem;
}
.card {
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 0.95rem;
  background: rgba(15, 23, 42, 0.72);
  display: grid;
  gap: 0.65rem;
  box-shadow: var(--shadow-sm);
}
.row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr) auto;
  gap: 0.45rem;
  align-items: end;
}
.field {
  display: grid;
  gap: 0.2rem;
  font-size: 0.85rem;
  min-width: 0;
}
input {
  width: 100%;
  min-width: 0;
  border-radius: 8px;
  border: 1px solid #334155;
  background: #0b1220;
  color: #fff;
  padding: 0.45rem 0.55rem;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}
.empty {
  color: #94a3b8;
  font-size: 0.88rem;
}
.error {
  color: #fca5a5;
  margin: 0;
}
.ghost {
  border: 1px solid #334155;
  border-radius: 8px;
  background: transparent;
  color: #cbd5e1;
  padding: 0.35rem 0.55rem;
}
.secondary {
  border: none;
  border-radius: 8px;
  background: #3b82f6;
  color: #fff;
  padding: 0.4rem 0.65rem;
}
.primary {
  border: none;
  border-radius: 8px;
  background: #16a34a;
  color: #fff;
  padding: 0.4rem 0.65rem;
}
.danger {
  border: none;
  border-radius: 8px;
  background: #7f1d1d;
  color: #fff;
  padding: 0.4rem 0.65rem;
}

@media (max-width: 640px) {
  .row {
    grid-template-columns: 1fr;
  }
}
</style>
