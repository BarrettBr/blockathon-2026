import { defineStore } from "pinia";
import apiHelper from "@/utils/apiHelper";

export const useSpendingGuardStore = defineStore("spendingGuard", {
  state: () => ({
    guard: null as any,
    loading: false,
    error: "",
  }),
  actions: {
    async load(userWalletAddress: string) {
      if (!userWalletAddress) return;
      this.loading = true;
      this.error = "";
      try {
        const res = await apiHelper.getSpendingGuard(userWalletAddress);
        this.guard = res.data.data;
      } catch (error: any) {
        this.error = error?.response?.data?.detail || "Failed to load guard";
      } finally {
        this.loading = false;
      }
    },

    async save(payload: { user_wallet_address: string; monthly_limit: number; currency: string }) {
      this.loading = true;
      this.error = "";
      try {
        const res = await apiHelper.setSpendingGuard(payload);
        this.guard = res.data.data;
      } catch (error: any) {
        this.error = error?.response?.data?.detail || "Failed to update guard";
        throw error;
      } finally {
        this.loading = false;
      }
    },
  },
});
