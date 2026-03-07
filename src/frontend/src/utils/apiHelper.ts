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
  bootstrapRlusdWallet: (payload: { user_seed: string; mint_amount: number }) =>
    api.post<ApiEnvelope<any>>("/wallets/bootstrap-rlusd", payload),
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

  approveSubscriptionRequest: (subscriptionId: number, payload: { username: string; user_seed: string }) =>
    api.post<ApiEnvelope<any>>(`/subscriptions/${subscriptionId}/approve`, payload),

  cancelSubscription: (
    subscriptionId: number,
    payload?: { username?: string; user_seed?: string },
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

  getHistory: (userWalletAddress: string, limit = 50) =>
    api.get<ApiEnvelope<any[]>>(`/history/${userWalletAddress}?limit=${limit}`),

  getDashboard: (userWalletAddress: string) =>
    api.get<ApiEnvelope<any>>(`/dashboard/${userWalletAddress}`),
};

export default apiHelper;
