import { defineStore } from "pinia";
import { ref, computed } from "vue";
import apiHelper from "@/utils/apiHelper";

export const useAuthStore = defineStore("auth", () => {
	const token = ref<string | null>(localStorage.getItem("token"));
	const username = ref<string | null>(localStorage.getItem("username"));

	const isLoggedIn = computed(() => !!token.value);

	async function login(u: string, password: string) {
		const resp = await apiHelper.login(u, password);
		token.value = resp.data.access_token;
		username.value = u;
		localStorage.setItem("token", token.value);
		localStorage.setItem("username", u);
	}

	async function register(u: string, password: string) {
		await apiHelper.register({ username: u, password });
		await login(u, password);
	}

	function logout() {
		token.value = null;
		username.value = null;
		localStorage.removeItem("token");
		localStorage.removeItem("username");
	}

	return { token, username, isLoggedIn, login, register, logout };
});
