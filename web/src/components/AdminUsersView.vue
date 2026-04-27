<script setup lang="ts">
import { computed, reactive, ref } from "vue";

import { ROLE_OPTIONS } from "../roles";
import type { AdminUser } from "../types";

const props = defineProps<{
  users: AdminUser[];
  loading: boolean;
  error: string;
}>();

const emit = defineEmits<{
  refresh: [];
  create: [payload: { login: string; password: string; role_code: string; full_name?: string | null; phone?: string | null }];
  update: [
    userId: number,
    payload: { login?: string; password?: string; role_code?: string; full_name?: string | null; phone?: string | null; is_active?: boolean }
  ];
  delete: [userId: number];
}>();

const creating = ref(false);
const editingUserId = ref<number | null>(null);

const createForm = reactive({
  login: "",
  password: "",
  role_code: "driver",
  full_name: "",
  phone: ""
});

const editForm = reactive({
  login: "",
  password: "",
  role_code: "",
  full_name: "",
  phone: "",
  is_active: true
});

const editableUser = computed(() => props.users.find((user) => user.id === editingUserId.value) ?? null);

function openCreate(): void {
  createForm.login = "";
  createForm.password = "";
  createForm.role_code = "driver";
  createForm.full_name = "";
  createForm.phone = "";
  creating.value = true;
}

function submitCreate(): void {
  emit("create", {
    login: createForm.login.trim(),
    password: createForm.password,
    role_code: createForm.role_code,
    full_name: createForm.full_name.trim() || null,
    phone: createForm.phone.trim() || null
  });
  creating.value = false;
}

function openEdit(user: AdminUser): void {
  editingUserId.value = user.id;
  editForm.login = user.login;
  editForm.password = "";
  editForm.role_code = user.role_code;
  editForm.full_name = user.full_name ?? "";
  editForm.phone = user.phone ?? "";
  editForm.is_active = user.is_active;
}

function submitEdit(): void {
  if (!editableUser.value) {
    return;
  }
  const payload: {
    login?: string;
    password?: string;
    role_code?: string;
    full_name?: string | null;
    phone?: string | null;
    is_active?: boolean;
  } = {};
  const login = editForm.login.trim();
  const fullName = editForm.full_name.trim();
  const phone = editForm.phone.trim();
  if (login && login !== editableUser.value.login) {
    payload.login = login;
  }
  if (editForm.password.trim()) {
    payload.password = editForm.password;
  }
  if (editForm.role_code && editForm.role_code !== editableUser.value.role_code) {
    payload.role_code = editForm.role_code;
  }
  if (fullName !== (editableUser.value.full_name ?? "")) {
    payload.full_name = fullName || null;
  }
  if (phone !== (editableUser.value.phone ?? "")) {
    payload.phone = phone || null;
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

function removeUser(user: AdminUser): void {
  if (!window.confirm(`Удалить пользователя ${user.login}?`)) {
    return;
  }
  emit("delete", user.id);
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

    <div v-if="!creating && !editableUser" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Логин</th>
            <th>ФИО</th>
            <th>Телефон</th>
            <th>Роль</th>
            <th>Активен</th>
            <th>Создан</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.id">
            <td>{{ user.id }}</td>
            <td>{{ user.login }}</td>
            <td>{{ user.full_name || "—" }}</td>
            <td>{{ user.phone || "—" }}</td>
            <td>{{ user.role_label }}</td>
            <td>{{ user.is_active ? "да" : "нет" }}</td>
            <td>{{ user.created_at ? new Date(user.created_at).toLocaleString() : "—" }}</td>
            <td class="row-actions">
              <button :disabled="loading" @click="openEdit(user)">Редактировать</button>
              <button :disabled="loading" @click="toggleActive(user)">
                {{ user.is_active ? "Заблокировать" : "Разблокировать" }}
              </button>
              <button class="danger" :disabled="loading" @click="removeUser(user)">Удалить</button>
            </td>
          </tr>
          <tr v-if="!users.length">
            <td colspan="8" class="empty">Пользователи не найдены</td>
          </tr>
        </tbody>
      </table>
    </div>

    <section v-if="creating" class="card form-card">
      <h2>Создать пользователя</h2>
      <label>
        Логин
        <input v-model="createForm.login" />
      </label>
      <label>
        Пароль
        <input v-model="createForm.password" type="password" />
      </label>
      <label>
        ФИО
        <input v-model="createForm.full_name" />
      </label>
      <label>
        Телефон
        <input v-model="createForm.phone" />
      </label>
      <label>
        Роль
        <select v-model="createForm.role_code">
          <option v-for="role in ROLE_OPTIONS" :key="role.role_code" :value="role.role_code">
            {{ role.role_label }}
          </option>
        </select>
      </label>
      <div class="actions">
        <button @click="submitCreate">Сохранить</button>
        <button @click="creating = false">Отмена</button>
      </div>
    </section>

    <section v-if="editableUser" class="card form-card">
      <h2>Редактировать пользователя #{{ editableUser.id }}</h2>
      <label>
        Логин
        <input v-model="editForm.login" />
      </label>
      <label>
        Новый пароль (необязательно)
        <input v-model="editForm.password" type="password" />
      </label>
      <label>
        ФИО
        <input v-model="editForm.full_name" />
      </label>
      <label>
        Телефон
        <input v-model="editForm.phone" />
      </label>
      <label>
        Роль
        <select v-model="editForm.role_code">
          <option v-for="role in ROLE_OPTIONS" :key="role.role_code" :value="role.role_code">
            {{ role.role_label }}
          </option>
        </select>
      </label>
      <label class="checkbox">
        <input v-model="editForm.is_active" type="checkbox" />
        Активен
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
  flex-wrap: wrap;
  gap: 0.6rem;
}
.actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.table-wrap {
  display: grid;
  gap: 0.6rem;
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}
th,
td {
  padding: 0.55rem;
  border-bottom: 1px solid #1f2937;
  text-align: left;
  white-space: normal;
  overflow-wrap: anywhere;
}
.row-actions {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
  align-items: center;
}
.row-actions button {
  max-width: 100%;
  flex: 1 1 auto;
}
td.row-actions {
  white-space: normal;
}
.danger {
  background: #7f1d1d;
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
input,
select {
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

@media (max-width: 760px) {
  .actions {
    width: 100%;
  }
  .table-wrap {
    border: 0;
    background: transparent;
  }
  table,
  thead,
  tbody,
  tr,
  th,
  td {
    display: block;
  }
  thead {
    display: none;
  }
  tr {
    border: 1px solid #374151;
    border-radius: 10px;
    background: #111827;
    padding: 0.5rem;
    margin-bottom: 0.5rem;
  }
  td {
    border: none;
    padding: 0.2rem 0;
    white-space: normal;
  }
  td::before {
    display: inline-block;
    min-width: 6.5rem;
    color: #9ca3af;
    font-size: 0.82rem;
  }
  td:nth-child(1)::before { content: "ID: "; }
  td:nth-child(2)::before { content: "Логин: "; }
  td:nth-child(3)::before { content: "ФИО: "; }
  td:nth-child(4)::before { content: "Телефон: "; }
  td:nth-child(5)::before { content: "Роль: "; }
  td:nth-child(6)::before { content: "Активен: "; }
  td:nth-child(7)::before { content: "Создан: "; }
  td:nth-child(8)::before { content: "Действия: "; }
  .row-actions {
    flex-wrap: wrap;
  }
}
</style>

