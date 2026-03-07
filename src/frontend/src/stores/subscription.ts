import { defineStore } from "pinia";
import apiHelper from "@/utils/apiHelper";

export const useSubscriptionStore = defineStore("subscription", {
  state: () => ({
    list: [] as any[],
    loading: false,
    error: "",
  }),
  actions: {
    async loadForUser(userWalletAddress: string) {
      if (!userWalletAddress) return;
      this.loading = true;
      this.error = "";
      try {
        const res = await apiHelper.listSubscriptionsForUser(userWalletAddress);
        this.list = res.data.data;
      } catch (error: any) {
        this.error = error?.response?.data?.detail || "Failed to load subscriptions";
      } finally {
        this.loading = false;
      }
    },

    async create(payload: any) {
      const res = await apiHelper.createSubscription(payload);
      return res.data.data;
    },

    async userApprove(subscriptionId: number, userSeed: string) {
      const res = await apiHelper.approveUserHandshake(subscriptionId, userSeed);
      return res.data.data;
    },

    async serviceApprove(subscriptionId: number, merchantSeed: string) {
      const res = await apiHelper.approveServiceHandshake(subscriptionId, merchantSeed);
      return res.data.data;
    },

    async process(subscriptionId: number, merchantSeed?: string) {
      const res = await apiHelper.processSubscription(subscriptionId, merchantSeed);
      return res.data.data;
    },

    async cancel(subscriptionId: number) {
      const res = await apiHelper.cancelSubscription(subscriptionId);
      return res.data.data;
    },
  },
});
