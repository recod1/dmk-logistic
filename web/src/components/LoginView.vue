<script setup lang="ts">
import { ref } from "vue";

const emit = defineEmits<{
  submit: [login: string, password: string];
}>();

defineProps<{
  loading: boolean;
  error: string;
}>();

const login = ref("");
const password = ref("");

function onSubmit() {
  emit("submit", login.value.trim(), password.value);
}
</script>

<template>
  <section class="card">
    <h1>Вход</h1>
    <p class="hint">Вход в систему</p>
    <form @submit.prevent="onSubmit">
      <label>
        Логин
        <input v-model="login" autocomplete="username" autocapitalize="off" required />
      </label>
      <label>
        Пароль
        <input v-model="password" type="password" autocomplete="current-password" required />
      </label>
      <button :disabled="loading" type="submit">{{ loading ? "Входим..." : "Войти" }}</button>
      <p v-if="error" class="error">{{ error }}</p>
    </form>
  </section>
</template>

<style scoped>
.card {
  max-width: 420px;
  margin: 0 auto;
  padding: 1.25rem;
  border-radius: 14px;
  background: #111827;
}
.hint {
  color: #9ca3af;
  margin-bottom: 1rem;
}
form {
  display: grid;
  gap: 0.75rem;
}
label {
  display: grid;
  gap: 0.35rem;
  font-size: 0.95rem;
}
input {
  padding: 0.6rem 0.75rem;
  border-radius: 10px;
  border: 1px solid #374151;
  background: #0b1220;
  color: #f9fafb;
}
button {
  margin-top: 0.5rem;
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 10px;
  padding: 0.65rem 1rem;
  cursor: pointer;
}
.error {
  color: #fda4af;
  margin: 0;
}
</style>

