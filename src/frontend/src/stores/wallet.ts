import { defineStore } from "pinia";
import apiHelper from "@/utils/apiHelper";

export interface ConnectedWallet {
  link_id: number;
  wallet_id: number;
  nickname: string;
  address: string;
  network: string;
  created_at?: string;
}

export const useWalletStore = defineStore("wallet", {
  state: () => ({
    wallets: [] as ConnectedWallet[],
    selectedWallet: null as ConnectedWallet | null,
    balance: null as any,
    aggregateBalance: null as any,
    loading: false,
    error: "",
    page: 1,
    pageSize: 10,
    total: 0,
    pages: 0,
  }),
  actions: {
    async loadWallets(page?: number) {
      const currentPage = page ?? this.page;
      this.loading = true;
      this.error = "";
      try {
        const res = await apiHelper.listWallets(currentPage, this.pageSize);
        const payload = res.data.data || {};
        this.wallets = payload.items || [];
        this.page = payload.page || currentPage;
        this.total = payload.total || 0;
        this.pages = payload.pages || 0;
        if (!this.selectedWallet && this.wallets.length > 0) {
          this.selectedWallet = this.wallets[0] || null;
        } else if (this.selectedWallet) {
          this.selectedWallet =
            this.wallets.find((w) => w.link_id === this.selectedWallet?.link_id) || this.wallets[0] || null;
        }
        await this.fetchAggregateBalance();
      } catch (error: any) {
        this.error = error?.response?.data?.detail || "Failed to load wallets";
      } finally {
        this.loading = false;
      }
    },

    async goToPage(page: number) {
      const target = Math.max(1, page);
      await this.loadWallets(target);
    },

    selectWallet(linkId: number) {
      this.selectedWallet = this.wallets.find((w) => w.link_id === linkId) || null;
      if (this.selectedWallet) {
        void this.fetchSelectedBalance();
      } else {
        this.balance = null;
      }
    },

    async connectWallet(seed: string, nickname: string) {
      this.loading = true;
      this.error = "";
      try {
        await apiHelper.connectWallet({ seed, nickname });
        await this.loadWallets(1);
        if (this.wallets.length > 0) {
          this.selectedWallet = this.wallets.find((w) => w.nickname === nickname) || this.wallets[0] || null;
          if (this.selectedWallet) {
            await this.fetchSelectedBalance();
          }
        }
      } catch (error: any) {
        this.error = error?.response?.data?.detail || "Wallet connect failed";
        throw error;
      } finally {
        this.loading = false;
      }
    },

    async removeConnectedWallet(linkId: number) {
      this.loading = true;
      this.error = "";
      try {
        await apiHelper.deleteConnectedWallet(linkId);
        if (this.selectedWallet?.link_id === linkId) {
          this.selectedWallet = null;
          this.balance = null;
        }
        await this.loadWallets(this.page);
        if (!this.selectedWallet && this.wallets.length > 0) {
          this.selectedWallet = this.wallets[0] || null;
        }
        if (this.selectedWallet) {
          await this.fetchSelectedBalance();
        }
      } catch (error: any) {
        this.error = error?.response?.data?.detail || "Failed to remove connected wallet";
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

    async fetchAggregateBalance() {
      this.loading = true;
      this.error = "";
      try {
        const res = await apiHelper.getAggregateBalance();
        this.aggregateBalance = res.data.data;
        return this.aggregateBalance;
      } catch (error: any) {
        this.error = error?.response?.data?.detail || "Aggregate balance fetch failed";
        throw error;
      } finally {
        this.loading = false;
      }
    },
  },
});
