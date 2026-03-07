import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

export interface ApiEnvelope<T> {
  message: string;
  data: T;
}

export const apiHelper = {
  health: () => api.get<ApiEnvelope<any>>("/health"),

  importWallet: (seed: string) => api.post<ApiEnvelope<any>>("/wallets/import", { seed }),
  createWallet: () => api.post<ApiEnvelope<any>>("/wallets/create"),
  listWallets: () => api.get<ApiEnvelope<any[]>>("/wallets"),
  getWalletBalance: (address: string) =>
    api.get<ApiEnvelope<any>>(`/wallets/${address}/balance`),

  sendXrpPayment: (payload: {
    sender_seed: string;
    destination_address: string;
    amount_xrp: number;
  }) => api.post<ApiEnvelope<any>>("/payments/send", payload),

  sendRlusdPayment: (payload: {
    sender_seed: string;
    destination_address: string;
    amount: number;
  }) => api.post<ApiEnvelope<any>>("/payments/send-rlusd", payload),

  listPayments: () => api.get<ApiEnvelope<any[]>>("/payments"),

  createSubscription: (payload: {
    user_wallet_address: string;
    merchant_wallet_address: string;
    user_seed: string;
    amount_xrp: number;
    interval_days: number;
    use_escrow: boolean;
  }) => api.post<ApiEnvelope<any>>("/subscriptions/create", payload),

  listSubscriptions: () => api.get<ApiEnvelope<any[]>>("/subscriptions"),
  listSubscriptionsForUser: (userWalletAddress: string) =>
    api.get<ApiEnvelope<any[]>>(`/subscriptions/user/${userWalletAddress}`),
  getSubscription: (subscriptionId: number) =>
    api.get<ApiEnvelope<any>>(`/subscriptions/${subscriptionId}`),

  approveUserHandshake: (subscriptionId: number, userSeed: string) =>
    api.post<ApiEnvelope<any>>(`/subscriptions/${subscriptionId}/handshake/user-approve`, {
      user_seed: userSeed,
    }),

  approveServiceHandshake: (subscriptionId: number, merchantSeed: string) =>
    api.post<ApiEnvelope<any>>(`/subscriptions/${subscriptionId}/handshake/service-approve`, {
      merchant_seed: merchantSeed,
    }),

  processSubscription: (subscriptionId: number, merchantSeed?: string) =>
    api.post<ApiEnvelope<any>>(`/subscriptions/${subscriptionId}/process`, {
      merchant_seed: merchantSeed,
    }),

  cancelSubscription: (subscriptionId: number) =>
    api.post<ApiEnvelope<any>>(`/subscriptions/${subscriptionId}/cancel`),

  setSpendingGuard: (payload: {
    user_wallet_address: string;
    monthly_limit: number;
    currency: string;
  }) => api.post<ApiEnvelope<any>>("/spending-guard/set", payload),

  getSpendingGuard: (userWalletAddress: string) =>
    api.get<ApiEnvelope<any>>(`/spending-guard/${userWalletAddress}`),

  getHistory: (userWalletAddress: string, limit = 50) =>
    api.get<ApiEnvelope<any[]>>(`/history/${userWalletAddress}?limit=${limit}`),

  getDashboard: (userWalletAddress: string) =>
    api.get<ApiEnvelope<any>>(`/dashboard/${userWalletAddress}`),
};

export default apiHelper;
