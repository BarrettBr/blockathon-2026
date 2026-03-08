import axios from "axios";

const API_BASE_URL =
	import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

const api = axios.create({
	baseURL: API_BASE_URL,
	headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
	const token = localStorage.getItem("token");
	if (token) {
		config.headers = config.headers || {};
		config.headers.Authorization = `Bearer ${token}`;
	}
	return config;
});

export interface ApiEnvelope<T> {
	message: string;
	data: T;
}

export const apiHelper = {
	health: () => api.get<ApiEnvelope<any>>("/health"),

		importWallet: (seed: string) => api.post<ApiEnvelope<any>>("/wallets/import", { seed }),
		connectWallet: (payload: { seed: string; nickname: string }) =>
	api.post<ApiEnvelope<any>>("/wallets/connect", payload),
	bootstrapRlusdWallet: (payload: { user_wallet_address: string; mint_amount: number }) =>
	api.post<ApiEnvelope<any>>("/wallets/bootstrap-rlusd", payload),
	createWallet: () => api.post<ApiEnvelope<any>>("/wallets/create"),
	listWallets: (page = 1, pageSize = 10) =>
		api.get<ApiEnvelope<any>>(`/wallets?page=${page}&page_size=${pageSize}`),
	deleteConnectedWallet: (linkId: number) =>
		api.delete<ApiEnvelope<any>>(`/wallets/connected/${linkId}`),
	getWalletBalance: (address: string) =>
		api.get<ApiEnvelope<any>>(`/wallets/${address}/balance`),
	getAggregateBalance: () => api.get<ApiEnvelope<any>>("/wallets/aggregate/balance"),

		sendXrpPayment: (payload: {
		from_address: string;
		destination_address: string;
		amount_xrp: number;
	}) => api.post<ApiEnvelope<any>>("/payments/send", payload),

		sendRlusdPayment: (payload: {
		from_address: string;
		destination_address: string;
		amount: number;
	}) => api.post<ApiEnvelope<any>>("/payments/send-rlusd", payload),

		listPayments: () => api.get<ApiEnvelope<any[]>>("/payments"),

		registerUserProfile: (payload: { username: string; wallet_address: string }) =>
	api.post<ApiEnvelope<any>>("/users/register", payload),

	saveVendor: (payload: {
		vendor_code: string;
		display_name: string;
		wallet_address: string;
		webhook_url?: string;
		shared_secret?: string;
	}) => api.post<ApiEnvelope<any>>("/vendors/upsert", payload),

		getVendorMe: (sharedSecret: string) =>
	api.get<ApiEnvelope<any>>("/vendors/me", {
		headers: { "X-Vendor-Secret": sharedSecret },
	}),

	updateVendorMe: (
		sharedSecret: string,
		payload: { display_name?: string; wallet_address?: string; webhook_url?: string },
	) =>
	api.patch<ApiEnvelope<any>>("/vendors/me", payload, {
		headers: { "X-Vendor-Secret": sharedSecret },
	}),

	regenerateVendorSecret: (sharedSecret: string) =>
	api.post<ApiEnvelope<any>>(
		"/vendors/me/secret/regenerate",
		{},
		{ headers: { "X-Vendor-Secret": sharedSecret } },
	),

	createSubscriptionRequest: (
		sharedSecret: string,
		payload: {
			vendor_tx_id: string;
			username: string;
			amount_xrp: number;
			interval_days: number;
		},
	) =>
	api.post<ApiEnvelope<any>>("/subscriptions/requests", payload, {
		headers: { "X-Vendor-Secret": sharedSecret },
	}),

	listPendingSubscriptionRequests: (username: string) =>
	api.get<ApiEnvelope<any[]>>(`/subscriptions/pending/${encodeURIComponent(username)}`),

	approveSubscriptionRequest: (subscriptionId: number, payload: { username: string }) =>
	api.post<ApiEnvelope<any>>(`/subscriptions/${subscriptionId}/approve`, payload),

	cancelSubscription: (
		subscriptionId: number,
		payload?: { username?: string },
		sharedSecret?: string,
	) =>
	api.post<ApiEnvelope<any>>(`/subscriptions/${subscriptionId}/cancel`, payload || {}, {
		headers: sharedSecret ? { "X-Vendor-Secret": sharedSecret } : undefined,
	}),

	getSubscriptionByContract: (contractHash: string) =>
	api.get<ApiEnvelope<any>>(`/subscriptions/contract/${contractHash}`),

	listSubscriptions: () => api.get<ApiEnvelope<any[]>>("/subscriptions"),
		getSubscription: (subscriptionId: number) =>
	api.get<ApiEnvelope<any>>(`/subscriptions/${subscriptionId}`),

	sendXrpPaymentAsVendor: (
		sharedSecret: string,
		payload: {
			sender_seed: string;
			destination_address: string;
			amount_xrp: number;
		},
	) =>
	api.post<ApiEnvelope<any>>("/payments/send", payload, {
		headers: { "X-Vendor-Secret": sharedSecret },
	}),

	setSpendingGuard: (payload: {
		user_wallet_address: string;
		monthly_limit: number;
		currency: string;
	}) => api.post<ApiEnvelope<any>>("/spending-guard/set", payload),

		getSpendingGuard: (userWalletAddress: string) =>
	api.get<ApiEnvelope<any>>(`/spending-guard/${userWalletAddress}`),

	aiReview: (payload: { wallet_addresses: string[]; days: number }) =>
	api.post<ApiEnvelope<any>>("/ai/review", payload),

	getHistory: (userWalletAddress: string, limit = 50) =>
	api.get<ApiEnvelope<any[]>>(`/history/${userWalletAddress}?limit=${limit}`),

		getDashboard: (userWalletAddress: string) =>
	api.get<ApiEnvelope<any>>(`/dashboard/${userWalletAddress}`),
	getAggregateDashboard: () => api.get<ApiEnvelope<any>>("/dashboard/aggregate"),

		createSnapshot: (payload: {
		title?: string;
		days?: number;
		start_date?: string;
		end_date?: string;
	}) => api.post<ApiEnvelope<any>>("/snapshots", payload),

		listSnapshots: () => api.get<ApiEnvelope<any[]>>("/snapshots"),

		getSnapshot: (snapshotId: number) => api.get<ApiEnvelope<any>>(`/snapshots/${snapshotId}`),

		askSnapshot: (snapshotId: number, question: string) =>
	api.post<ApiEnvelope<any>>(`/snapshots/${snapshotId}/ask`, { question }),

	// Add to the apiHelper object
	register: (payload: { username: string; password: string }) =>
	api.post<ApiEnvelope<any>>("/auth/register", null, { params: payload }),

	login: (username: string, password: string) => {
		const form = new URLSearchParams();
		form.append("username", username);
		form.append("password", password);
		return api.post<{ access_token: string; token_type: string }>("/auth/token", form, {
			headers: { "Content-Type": "application/x-www-form-urlencoded" },
		});
	},
};


export default apiHelper;
