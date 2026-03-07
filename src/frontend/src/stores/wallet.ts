import { defineStore } from "pinia";
import apiHelper from "@/utils/apiHelper";

export interface WalletRecord {
  id: number;
  address: string;
  seed: string;
  network: string;
  created_at?: string;
}

export const useWalletStore = defineStore("wallet", {
  state: () => ({
    wallets: [] as WalletRecord[],
    selectedWallet: null as WalletRecord | null,
    balance: null as any,
    loading: false,
    error: "",
  }),
  actions: {
    async loadWallets() {
      this.loading = true;
      this.error = "";
      try {
        const res = await apiHelper.listWallets();
        this.wallets = res.data.data;
        if (!this.selectedWallet && this.wallets.length > 0) {
          this.selectedWallet = this.wallets[0] || null;
        }
      } catch (error: any) {
        this.error = error?.response?.data?.detail || "Failed to load wallets";
      } finally {
        this.loading = false;
      }
    },

    selectWallet(address: string) {
      this.selectedWallet = this.wallets.find((w) => w.address === address) || null;
      if (this.selectedWallet) {
        void this.fetchSelectedBalance();
      } else {
        this.balance = null;
      }
    },

    async importWallet(seed: string) {
      this.loading = true;
      this.error = "";
      try {
        const res = await apiHelper.importWallet(seed);
        const wallet = res.data.data as WalletRecord;
        const existing = this.wallets.find((w) => w.address === wallet.address);
        if (!existing) {
          this.wallets.unshift(wallet);
        }
        this.selectedWallet = wallet;
        return wallet;
      } catch (error: any) {
        this.error = error?.response?.data?.detail || "Wallet import failed";
        throw error;
      } finally {
        this.loading = false;
      }
    },

    async createWallet() {
      this.loading = true;
      this.error = "";
      try {
        const res = await apiHelper.createWallet();
        const wallet = res.data.data as WalletRecord;
        this.wallets.unshift(wallet);
        this.selectedWallet = wallet;
        return wallet;
      } catch (error: any) {
        this.error = error?.response?.data?.detail || "Wallet create failed";
        throw error;
      } finally {
        this.loading = false;
      }
    },

    async fetchSelectedBalance() {
      if (!this.selectedWallet) return null;
      this.loading = true;
      this.error = "";
      try {
        const res = await apiHelper.getWalletBalance(this.selectedWallet.address);
        this.balance = res.data.data;
        return this.balance;
      } catch (error: any) {
        this.error = error?.response?.data?.detail || "Balance fetch failed";
        throw error;
      } finally {
        this.loading = false;
      }
    },
  },
});
