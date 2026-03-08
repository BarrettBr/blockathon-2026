<script setup lang="ts">
import { onMounted } from "vue";
import { useWalletStore } from "@/stores/wallet";
import { useLayoutStore } from "@/stores/layout";
import AppSidebar from "./AppSidebar.vue";
import AppTopbar from "./AppTopbar.vue";

const wallet = useWalletStore();
const layout = useLayoutStore();

onMounted(async () => {
  layout.initTheme();
  await wallet.loadWallets();
  if (wallet.selectedWallet) {
    await wallet.fetchSelectedBalance();
  }
  await wallet.fetchAggregateBalance();
});
</script>

<template>
  <div class="layout">
    <AppSidebar />

    <div
      class="overlay"
      :class="{ active: layout.mobileMenuOpen }"
      @click="layout.closeMobileMenu"
    />

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
  background: var(--app-bg);
}

.overlay {
  position: fixed;
  inset: 0;
  background: rgba(7, 18, 34, 0.44);
  z-index: 15;
  display: none;
}

.main-wrap {
  margin-left: 260px;
  min-height: 100vh;
}

.content {
  padding: calc(74px + 1.2rem) 1.2rem 1.2rem;
  max-width: 1280px;
  margin: 0 auto;
  color: var(--text-primary);
}

@media (max-width: 991px) {
  .overlay.active {
    display: block;
  }

  .main-wrap {
    margin-left: 0;
  }
}
</style>
