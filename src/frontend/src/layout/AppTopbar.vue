<script setup lang="ts">
import { computed } from "vue";
import { useLayoutStore } from "@/stores/layout";
import { useWalletStore } from "@/stores/wallet";

const layout = useLayoutStore();
const wallet = useWalletStore();

const walletBalance = computed(() => {
  const value = wallet.balance?.rlusd_balance;
  if (typeof value !== "number") return "--";
  return value.toFixed(2);
});
</script>

<template>
  <header class="topbar">
    <button class="menu-btn" @click="layout.toggleSidebar">☰</button>

    <div class="title">Consumer-Controlled Payments on XRPL</div>

    <div class="right">
      <div class="balance">Balance: {{ walletBalance }} RLUSD</div>
      <div class="account">My Account</div>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  height: 68px;
  border-bottom: 1px solid #d8e6ff;
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0 1.25rem;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(8px);
  position: sticky;
  top: 0;
  z-index: 10;
}

.menu-btn {
  border: none;
  background: #ecf3ff;
  color: #1f4f90;
  border-radius: 8px;
  width: 34px;
  height: 34px;
  font-size: 1rem;
  cursor: pointer;
  display: none;
}

.title {
  color: #3b5f88;
  font-weight: 600;
  font-size: 0.98rem;
}

.right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 1rem;
}

.balance {
  color: #274f84;
  font-weight: 700;
}

.account {
  color: #345f94;
  font-weight: 600;
}

@media (max-width: 900px) {
  .menu-btn {
    display: inline-grid;
    place-items: center;
  }

  .title {
    display: none;
  }

  .balance {
    font-size: 0.85rem;
  }
}
</style>
