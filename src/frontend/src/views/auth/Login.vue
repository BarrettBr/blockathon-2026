<script setup lang="ts">
	import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();

const mode = ref<"login" | "register">("login");
const username = ref("");
const password = ref("");
const error = ref("");
const loading = ref(false);

async function submit() {
  error.value = "";
  loading.value = true;
  try {
	if (mode.value === "login") {
	  await auth.login(username.value, password.value);
	} else {
	  await auth.register(username.value, password.value);
	}
	router.push("/dashboard");
  } catch (e: any) {
	error.value = e?.response?.data?.detail || "Something went wrong";
  } finally {
	loading.value = false;
  }
}
</script>

<template>
	<section class="page">
		<article class="card">
			<h2>EquiPay</h2>
			<div class="tabs">
				<button :class="{ active: mode === 'login' }" @click="mode = 'login'">Login</button>
				<button :class="{ active: mode === 'register' }" @click="mode = 'register'">Register</button>
			</div>

			<div class="fields">
				<input v-model="username" placeholder="Username" />
				<input v-model="password" type="password" placeholder="Password" />
			</div>

			<p v-if="error" class="error">{{ error }}</p>
			<button class="submit" :disabled="loading" @click="submit">
				{{ loading ? "..." : mode === "login" ? "Login" : "Register" }}
			</button>
		</article>
	</section>
</template>

<style scoped>
.page { min-height: 100vh; display: grid; place-items: center; background: var(--app-bg); }
.card {
	background: var(--surface-panel);
	border: 1px solid var(--border-color);
	border-radius: 12px;
	padding: 2rem;
	width: 100%;
	max-width: 360px;
	display: flex;
	flex-direction: column;
	gap: 1rem;
}
.tabs { display: flex; gap: 0.5rem; }
.tabs button { flex: 1; padding: 0.4rem; border: 1px solid var(--border-color); border-radius: 6px; background: none; cursor: pointer; }
.tabs button.active { background: var(--accent-2); color: white; border-color: var(--accent-2); }
.fields { display: flex; flex-direction: column; gap: 0.5rem; }
.fields input { padding: 0.5rem 0.75rem; border: 1px solid var(--border-color); border-radius: 6px; font-size: 0.95rem; }
.submit { padding: 0.6rem; background: linear-gradient(130deg, var(--accent-1), var(--accent-2)); color: white; border: none; border-radius: 6px; font-weight: 700; cursor: pointer; }
.submit:disabled { opacity: 0.6; }
.error { color: #c0392b; font-size: 0.85rem; margin: 0; }
</style>
