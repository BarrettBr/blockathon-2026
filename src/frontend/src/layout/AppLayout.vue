<script setup lang="ts">
import { onMounted } from "vue";
import { useWalletStore } from "@/stores/wallet";
import AppSidebar from "./AppSidebar.vue";
import AppTopbar from "./AppTopbar.vue";

const wallet = useWalletStore();

onMounted(async () => {
  await wallet.loadWallets();
  if (wallet.selectedWallet) {
    await wallet.fetchSelectedBalance();
  }
});
</script>

<template>
  <div class="layout">
    <AppSidebar />

    <div class="overlay" />

    <div class="main-wrap">
      <AppTopbar />
      <main class="content">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout {
  min-height: 100vh;
}

.main-wrap {
  margin-left: 260px;
  min-height: 100vh;
}

.content {
  padding: 1.2rem;
  max-width: 1280px;
  margin: 0 auto;
}

@media (max-width: 991px) {
  .main-wrap {
    margin-left: 0;
  }
}
</style>
