import axios from "axios";
import router from "@/router";

const API_BASE_URL =
	import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

const api = axios.create({
	baseURL: API_BASE_URL,
	headers: {
		"Content-Type": "application/json",
	},
});

// Attach auth token if logged in
api.interceptors.request.use((config) => {
	const auth = JSON.parse(localStorage.getItem("auth") || "{}");
	if (auth.token) {
		config.headers.Authorization = `Bearer ${auth.token}`;
	}
	return config;
});

// Handle the 401 response error
api.interceptors.response.use(
	(response) => response,
	(error) => {
		if (error.response?.status === 401) {
			router.push("/login");
		}
		return Promise.reject(error);
	},
);

export default {
	login: async (username: string, password: string) => {
		return api.post("/auth/login", { username, password });
	},
	logout: async () => {
		return api.post("/auth/logout");
	},
	getUserProfile: async () => {
		return api.get("/auth/me");
	},
};

