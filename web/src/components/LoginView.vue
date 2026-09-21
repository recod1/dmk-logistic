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
  <section class="login-screen">
    <div class="brand">
      <span class="logo">ДМК</span>
      <h1>Логистика</h1>
      <p class="hint">Войдите, чтобы открыть рейсы, чаты и расчёты</p>
    </div>
    <form class="card" @submit.prevent="onSubmit">
      <label>
        Логин
        <input v-model="login" autocomplete="username" autocapitalize="off" required placeholder="Ваш логин" />
      </label>
      <label>
        Пароль
        <input v-model="password" type="password" autocomplete="current-password" required placeholder="Пароль" />
      </label>
      <button :disabled="loading" type="submit">{{ loading ? "Входим…" : "Войти" }}</button>
      <p v-if="error" class="error">{{ error }}</p>
    </form>
  </section>
</template>

<style scoped>
.login-screen {
  min-height: 100%;
  display: grid;
  align-content: center;
  justify-items: center;
  gap: 1.25rem;
  padding: 1rem 0 2rem;
}
.brand {
  text-align: center;
}
.logo {
  display: inline-grid;
  place-items: center;
  min-width: 3.4rem;
  height: 2.2rem;
  padding: 0 0.7rem;
  border-radius: 999px;
  background: linear-gradient(180deg, #3b82f6, #1d4ed8);
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.14em;
}
h1 {
  margin: 0.7rem 0 0.3rem;
  font-size: 1.7rem;
  letter-spacing: -0.03em;
}
.hint {
  color: var(--text-muted);
  margin: 0;
  font-size: 0.95rem;
}
.card {
  width: min(420px, 100%);
  margin: 0 auto;
  padding: 1.2rem;
  border-radius: 18px;
  background: rgba(17, 24, 39, 0.88);
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
  backdrop-filter: blur(16px);
}
form {
  display: grid;
  gap: 0.8rem;
}
label {
  display: grid;
  gap: 0.35rem;
  font-size: 0.92rem;
  color: #cbd5e1;
}
input {
  padding: 0.72rem 0.8rem;
  border-radius: 12px;
  border: 1px solid var(--border-strong);
  background: var(--bg-elevated);
  color: var(--text);
}
button {
  margin-top: 0.2rem;
  min-height: 46px;
  background: linear-gradient(180deg, #3b82f6, #2563eb);
  color: #fff;
  border: none;
  border-radius: 12px;
  padding: 0.7rem 1rem;
  font-weight: 650;
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.28);
}
.error {
  color: #fda4af;
  margin: 0;
  font-size: 0.9rem;
}
</style>
