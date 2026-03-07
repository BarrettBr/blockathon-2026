import { defineStore } from "pinia";
import apiHelper from "@/utils/apiHelper";

export const useDashboardStore = defineStore("dashboard", {
  state: () => ({
    data: null as any,
    loading: false,
    error: "",
  }),
  actions: {
    async loadDashboard(userWalletAddress: string) {
      if (!userWalletAddress) return;
      this.loading = true;
      this.error = "";
      try {
        const res = await apiHelper.getDashboard(userWalletAddress);
        this.data = res.data.data;
      } catch (error: any) {
        this.error = error?.response?.data?.detail || "Failed to load dashboard";
      } finally {
        this.loading = false;
      }
    },
  },
});
