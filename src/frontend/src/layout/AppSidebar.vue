<script setup lang="ts">
import AppMenu from "./AppMenu.vue";
import { useLayoutStore } from "@/stores/layout";

const layout = useLayoutStore();
</script>

<template>
  <aside
    class="sidebar"
    :class="{
      collapsed: !layout.sidebarOpen,
      mobileOpen: layout.mobileMenuOpen,
    }"
  >
    <div class="brand">
      <div class="logo">EP</div>
      <div class="wordmark">EquiPay</div>
    </div>

    <AppMenu />

    <div class="footer">XRPL Devnet</div>
  </aside>
</template>

<style scoped>
.sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  width: 260px;
  background: linear-gradient(180deg, #f7fbff 0%, #edf4ff 100%);
  border-right: 1px solid #d8e6ff;
  padding: 1rem;
  display: grid;
  grid-template-rows: auto 1fr auto;
  gap: 1rem;
  z-index: 20;
  transition: transform 0.2s ease;
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.2rem 0.4rem;
}

.logo {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: linear-gradient(145deg, #2563eb, #1f57c8);
  color: white;
  font-weight: 800;
  display: grid;
  place-items: center;
  font-size: 0.72rem;
}

.wordmark {
  font-weight: 800;
  color: #20436f;
  font-size: 1.2rem;
}

.footer {
  font-size: 0.78rem;
  color: #4b6f9d;
  padding: 0.3rem;
}

:deep(.menu) {
  align-self: start;
}

@media (max-width: 991px) {
  .sidebar {
    transform: translateX(-100%);
  }

  .sidebar.mobileOpen {
    transform: translateX(0);
  }
}
</style>
