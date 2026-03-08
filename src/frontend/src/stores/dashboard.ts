import { defineStore } from "pinia";
import apiHelper from "@/utils/apiHelper";

let dashboardInFlight: Promise<any> | null = null;

export const useDashboardStore = defineStore("dashboard", {
  state: () => ({
    data: null as any,
    loading: false,
    error: "",
    fetchedAt: 0,
  }),
  actions: {
    async loadDashboard(_userWalletAddress?: string, force = false) {
      const now = Date.now();
      if (!force && this.data && now - this.fetchedAt < 2000) {
        return this.data;
      }
      if (dashboardInFlight) {
        return await dashboardInFlight;
      }
      this.loading = true;
      this.error = "";
      dashboardInFlight = (async () => {
        const res = await apiHelper.getAggregateDashboard();
        this.data = res.data.data;
        this.fetchedAt = Date.now();
        return this.data;
      })();
      try {
        return await dashboardInFlight;
      } catch (error: any) {
        this.error = error?.response?.data?.detail || "Failed to load dashboard";
      } finally {
        dashboardInFlight = null;
        this.loading = false;
      }
    },
  },
});
