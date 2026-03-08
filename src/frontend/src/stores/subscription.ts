import { defineStore } from "pinia";
import apiHelper from "@/utils/apiHelper";

export const useSubscriptionStore = defineStore("subscription", {
  state: () => ({
    list: [] as any[],
    pending: [] as any[],
    history: [] as any[],
    vendorProfile: null as any,
    loading: false,
    error: "",
  }),
  getters: {
    activeSubscriptions(state) {
      return state.list.filter((row) => row.status === "active");
    },
    cancelledSubscriptions(state) {
      return state.list.filter((row) => row.status === "cancelled");
    },
  },
  actions: {
    async registerUserProfile(username: string, walletAddress: string) {
      const res = await apiHelper.registerUserProfile({ username, wallet_address: walletAddress });
      return res.data.data;
    },

    async saveVendor(payload: {
      vendor_code: string;
      display_name: string;
      wallet_address: string;
      webhook_url?: string;
      vendor_photo_url?: string;
      shared_secret?: string;
    }) {
      const res = await apiHelper.saveVendor(payload);
      return res.data.data;
    },

    async loadVendorMe(sharedSecret: string) {
      const res = await apiHelper.getVendorMe(sharedSecret);
      this.vendorProfile = res.data.data;
      return this.vendorProfile;
    },

    async updateVendorMe(
      sharedSecret: string,
      payload: { display_name?: string; wallet_address?: string; webhook_url?: string; vendor_photo_url?: string },
    ) {
      const res = await apiHelper.updateVendorMe(sharedSecret, payload);
      this.vendorProfile = res.data.data;
      return this.vendorProfile;
    },

    async regenerateVendorSecret(sharedSecret: string) {
      const res = await apiHelper.regenerateVendorSecret(sharedSecret);
      return res.data.data;
    },

    async uploadVendorPhoto(sharedSecret: string, file: File) {
      const res = await apiHelper.uploadVendorPhoto(sharedSecret, file);
      if (this.vendorProfile) {
        this.vendorProfile.vendor_photo_url = res.data.data.vendor_photo_url;
      }
      return res.data.data;
    },

    async createRequest(
      sharedSecret: string,
      payload: {
        vendor_tx_id: string;
        username: string;
        amount_xrp: number;
        interval_days: number;
        interval_seconds?: number;
      },
    ) {
      const res = await apiHelper.createSubscriptionRequest(sharedSecret, payload);
      return res.data.data;
    },

    async loadPending(username: string) {
      if (!username) {
        this.pending = [];
        return [];
      }
      this.loading = true;
      this.error = "";
      try {
        const res = await apiHelper.listPendingSubscriptionRequests(username);
        this.pending = res.data.data;
        return this.pending;
      } catch (error: any) {
        this.error = error?.response?.data?.detail || "Failed to load pending requests";
        throw error;
      } finally {
        this.loading = false;
      }
    },

    async approve(subscriptionId: number) {
		const res = await apiHelper.approveSubscriptionRequest(subscriptionId);
		return res.data.data;
	},

	async cancel(subscriptionId: number) {
		const res = await apiHelper.cancelSubscription(subscriptionId);
		return res.data.data;
	},

    async loadAllForWallet(walletAddress: string) {
      if (!walletAddress) {
        this.list = [];
        return [];
      }
      this.loading = true;
      this.error = "";
      try {
        const res = await apiHelper.listSubscriptions();
        this.list = (res.data.data || []).filter(
          (row: any) =>
            (row.user_wallet_address === walletAddress || row.merchant_wallet_address === walletAddress) &&
            row.status === "active",
        );
        return this.list;
      } catch (error: any) {
        this.error = error?.response?.data?.detail || "Failed to load subscriptions";
        throw error;
      } finally {
        this.loading = false;
      }
    },

    async loadHistoryForWallet(walletAddress: string, limit = 100) {
      if (!walletAddress) {
        this.history = [];
        return [];
      }
      const res = await apiHelper.getHistory(walletAddress, limit);
      this.history = (res.data.data || []).filter((row: any) =>
        String(row.event_type || "").startsWith("subscription"),
      );
      return this.history;
    },
  },
});
