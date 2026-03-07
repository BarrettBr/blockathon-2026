import { defineStore } from "pinia";
import apiHelper from "@/utils/apiHelper";

export const useHistoryStore = defineStore("history", {
  state: () => ({
    entries: [] as any[],
    loading: false,
    error: "",
  }),
  actions: {
    async load(userWalletAddress: string, limit = 50) {
      if (!userWalletAddress) return;
      this.loading = true;
      this.error = "";
      try {
        const res = await apiHelper.getHistory(userWalletAddress, limit);
        this.entries = res.data.data;
      } catch (error: any) {
        this.error = error?.response?.data?.detail || "Failed to load history";
      } finally {
        this.loading = false;
      }
    },
  },
});
