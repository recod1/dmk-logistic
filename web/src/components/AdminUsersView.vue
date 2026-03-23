<script setup lang="ts">
import { computed, reactive, ref } from "vue";

import type { AdminUser } from "../types";

const props = defineProps<{
  users: AdminUser[];
  loading: boolean;
  error: string;
}>();

const emit = defineEmits<{
  refresh: [];
  create: [payload: { login: string; password: string; role: string }];
  update: [userId: number, payload: { login?: string; password?: string; role?: string; is_active?: boolean }];
}>();

const creating = ref(false);
const editingUserId = ref<number | null>(null);

const createForm = reactive({
  login: "",
  password: "",
  role: "driver"
});

const editForm = reactive({
  login: "",
  password: "",
  role: "",
  is_active: true
});

const editableUser = computed(() => props.users.find((user) => user.id === editingUserId.value) ?? null);

function openCreate(): void {
  createForm.login = "";
  createForm.password = "";
  createForm.role = "driver";
  creating.value = true;
}

function submitCreate(): void {
  emit("create", {
    login: createForm.login.trim(),
    password: createForm.password,
    role: createForm.role.trim()
  });
  creating.value = false;
}

function openEdit(user: AdminUser): void {
  editingUserId.value = user.id;
  editForm.login = user.login;
  editForm.password = "";
  editForm.role = user.role;
  editForm.is_active = user.is_active;
}

function submitEdit(): void {
  if (!editableUser.value) {
    return;
  }
  const payload: { login?: string; password?: string; role?: string; is_active?: boolean } = {};
  const login = editForm.login.trim();
  const role = editForm.role.trim();
  if (login && login !== editableUser.value.login) {
    payload.login = login;
  }
  if (editForm.password.trim()) {
    payload.password = editForm.password;
  }
  if (role && role !== editableUser.value.role) {
    payload.role = role;
  }
  if (editForm.is_active !== editableUser.value.is_active) {
    payload.is_active = editForm.is_active;
  }
  emit("update", editableUser.value.id, payload);
  editingUserId.value = null;
}

function toggleActive(user: AdminUser): void {
  emit("update", user.id, { is_active: !user.is_active });
}
</script>

<template>
  <section class="users-wrap">
    <div class="head-row">
      <h1>Пользователи</h1>
      <div class="actions">
        <button :disabled="loading" @click="emit('refresh')">Обновить</button>
        <button :disabled="loading" @click="openCreate">Создать</button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Login</th>
            <th>Role</th>
            <th>Active</th>
            <th>Created</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.id">
            <td>{{ user.id }}</td>
            <td>{{ user.login }}</td>
            <td>{{ user.role }}</td>
            <td>{{ user.is_active ? "yes" : "no" }}</td>
            <td>{{ user.created_at ? new Date(user.created_at).toLocaleString() : "—" }}</td>
            <td class="row-actions">
              <button :disabled="loading" @click="openEdit(user)">Редактировать</button>
              <button :disabled="loading" @click="toggleActive(user)">
                {{ user.is_active ? "Заблокировать" : "Разблокировать" }}
              </button>
            </td>
          </tr>
          <tr v-if="!users.length">
            <td colspan="6" class="empty">Пользователи не найдены</td>
          </tr>
        </tbody>
      </table>
    </div>

    <section v-if="creating" class="card form-card">
      <h2>Создать пользователя</h2>
      <label>
        Login
        <input v-model="createForm.login" />
      </label>
      <label>
        Password
        <input v-model="createForm.password" type="password" />
      </label>
      <label>
        Role
        <input v-model="createForm.role" />
      </label>
      <div class="actions">
        <button @click="submitCreate">Сохранить</button>
        <button @click="creating = false">Отмена</button>
      </div>
    </section>

    <section v-if="editableUser" class="card form-card">
      <h2>Редактировать пользователя #{{ editableUser.id }}</h2>
      <label>
        Login
        <input v-model="editForm.login" />
      </label>
      <label>
        New password (optional)
        <input v-model="editForm.password" type="password" />
      </label>
      <label>
        Role
        <input v-model="editForm.role" />
      </label>
      <label class="checkbox">
        <input v-model="editForm.is_active" type="checkbox" />
        is_active
      </label>
      <div class="actions">
        <button @click="submitEdit">Сохранить</button>
        <button @click="editingUserId = null">Отмена</button>
      </div>
    </section>
  </section>
</template>

<style scoped>
.users-wrap {
  display: grid;
  gap: 0.8rem;
}
.head-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.actions {
  display: flex;
  gap: 0.5rem;
}
.table-wrap {
  overflow-x: auto;
  border: 1px solid #374151;
  border-radius: 10px;
  background: #111827;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th,
td {
  padding: 0.55rem;
  border-bottom: 1px solid #1f2937;
  text-align: left;
  white-space: nowrap;
}
.row-actions {
  display: flex;
  gap: 0.4rem;
}
.empty {
  text-align: center;
  color: #9ca3af;
}
.error {
  color: #fca5a5;
}
.form-card {
  display: grid;
  gap: 0.55rem;
}
label {
  display: grid;
  gap: 0.3rem;
}
input {
  border-radius: 8px;
  border: 1px solid #374151;
  background: #0b1220;
  color: #fff;
  padding: 0.45rem 0.6rem;
}
.checkbox {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
</style>

