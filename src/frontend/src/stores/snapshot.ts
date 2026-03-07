import { defineStore } from "pinia";
import apiHelper from "@/utils/apiHelper";

export const useSnapshotStore = defineStore("snapshot", {
  state: () => ({
    list: [] as any[],
    selected: null as any,
    answer: "",
    loading: false,
    error: "",
  }),
  actions: {
    async create(payload: { title?: string; days?: number; start_date?: string; end_date?: string }) {
      const res = await apiHelper.createSnapshot(payload);
      return res.data.data;
    },

    async loadList() {
      this.loading = true;
      this.error = "";
      try {
        const res = await apiHelper.listSnapshots();
        this.list = res.data.data || [];
      } catch (error: any) {
        this.error = error?.response?.data?.detail || "Failed to load snapshots";
      } finally {
        this.loading = false;
      }
    },

    async open(snapshotId: number) {
      this.loading = true;
      this.error = "";
      try {
        const res = await apiHelper.getSnapshot(snapshotId);
        this.selected = res.data.data;
        this.answer = "";
        return this.selected;
      } catch (error: any) {
        this.error = error?.response?.data?.detail || "Failed to open snapshot";
        throw error;
      } finally {
        this.loading = false;
      }
    },

    async ask(snapshotId: number, question: string) {
      this.loading = true;
      this.error = "";
      try {
        const res = await apiHelper.askSnapshot(snapshotId, question);
        this.answer = res.data.data?.answer || "";
        return this.answer;
      } catch (error: any) {
        this.error = error?.response?.data?.detail || "Failed to ask snapshot question";
        throw error;
      } finally {
        this.loading = false;
      }
    },
  },
});
