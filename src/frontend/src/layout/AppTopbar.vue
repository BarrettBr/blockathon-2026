<script setup lang="ts">
import { ref, computed, onBeforeUnmount, onMounted, watch } from "vue";
import { useLayoutStore } from "@/stores/layout";
import { useWalletStore } from "@/stores/wallet";
import Menu from "primevue/menu";
import Button from "primevue/button";
import { useAuthStore } from "@/stores/auth";
import { useRouter } from "vue-router";

const layout = useLayoutStore();
const wallet = useWalletStore();
const auth = useAuthStore();
const router = useRouter();
const menu = ref();

const items = ref([
  { label: 'My Profile', icon: 'pi pi-user' },
  { label: 'Settings', icon: 'pi pi-cog' },
  { separator: true },
  { label: 'Logout', icon: 'pi pi-sign-out', command: () => { auth.logout(); router.push("/login"); } }
]);

const toggleMenu = (event: Event) => {
  // event.currentTarget ensures it anchors to the <Button>, not the inner <i> or <span>
  menu.value.toggle(event); 
};

const walletBalance = computed(() => {
  const total = Number(wallet.aggregateBalance?.total_balance_rlusd);
  if (Number.isFinite(total)) return total.toFixed(2);

  const direct = Number(wallet.balance?.rlusd_balance);
  if (Number.isFinite(direct)) return direct.toFixed(2);
  return "--";
});

const accountLabel = computed(() => auth.username || "My Account");
const themeIcon = computed(() =>
  layout.theme === "dark" ? "pi pi-sun" : "pi pi-moon",
);
const themeLabel = computed(() =>
  layout.theme === "dark" ? "Switch to light mode" : "Switch to dark mode",
);

onMounted(async () => {
  if (!wallet.aggregateBalance) {
    await wallet.fetchAggregateBalance();
  }
});

watch(
  () => wallet.wallets.length,
  async () => {
    await wallet.fetchAggregateBalance(true);
  },
);

const balancePoll = window.setInterval(() => {
  void wallet.fetchAggregateBalance(true);
}, 2000);

onBeforeUnmount(() => {
  window.clearInterval(balancePoll);
});
</script>

<template>
  <header class="topbar">
    <button class="menu-btn" @click="layout.toggleSidebar">☰</button>
    <div class="brand">
      <div class="title">EquiPay</div>
      <div class="tagline">Bank-simple subscription payments on XRPL</div>
    </div>

	<div class="right">
		<div class="balance">Balance: {{ walletBalance }} RLUSD</div>
    <button class="theme-btn" :title="themeLabel" :aria-label="themeLabel" @click="layout.toggleTheme">
      <i :class="themeIcon"></i>
    </button>

		<Button 
			 text 
			 class="account-btn"
			 @click="toggleMenu" 
			 >
			 <i class="pi pi-user-circle" style="font-size: 1.5rem; margin-right: 0.5rem;"></i>
			 <span>{{ accountLabel }}</span>
			 <i class="pi pi-chevron-down" style="margin-left: 0.5rem; font-size: 0.8rem;"></i>
		</Button>

		<Menu ref="menu" :model="items" :popup="true" />
	</div>
  </header>
</template>

<style scoped>
.account-btn {
  color: var(--text-strong) !important;
  font-weight: 600 !important;
  padding: 0.5rem 0.75rem !important;
  border-radius: 12px !important;
}

.account-btn:hover {
  background: var(--surface-soft) !important;
}

.topbar {
  height: 74px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0 1.25rem;
  background: var(--topbar-bg);
  backdrop-filter: blur(8px);
  position: fixed;
  top: 0;
  left: 260px;
  right: 0;
  z-index: 18;
}

.menu-btn {
  border: none;
  background: var(--surface-soft);
  color: var(--text-strong);
  border-radius: 8px;
  width: 34px;
  height: 34px;
  font-size: 1rem;
  cursor: pointer;
  display: none;
}

.title {
  color: var(--text-strong);
  font-weight: 800;
  font-size: 1.02rem;
  line-height: 1.1;
}

.brand {
  display: inline-flex;
  align-items: baseline;
  gap: 0.65rem;
}

.tagline {
  color: var(--text-muted);
  font-size: 0.82rem;
  font-weight: 600;
  letter-spacing: 0.01em;
}

.right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 1rem;
}

.balance {
  color: var(--text-strong);
  font-weight: 700;
}

.account {
  color: var(--text-strong);
  font-weight: 600;
}

.theme-btn {
  width: 34px;
  height: 34px;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: var(--surface-panel);
  color: var(--text-strong);
  display: inline-grid;
  place-items: center;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.2s ease;
}

.theme-btn:hover {
  background: var(--surface-soft);
  transform: translateY(-1px);
}

@media (max-width: 991px) {
  .topbar {
    left: 0;
  }

  .menu-btn {
    display: inline-grid;
    place-items: center;
  }

  .title {
    font-size: 0.95rem;
  }

  .tagline {
    display: none;
  }

  .balance {
    font-size: 0.85rem;
  }
}


/* --- POPUP MENU CONTAINER --- */
:deep(.p-menu) {
  background: var(--surface-panel);
  min-width: 200px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08); /* Smoother shadow */
  padding: 0.5rem;
  z-index: 1000; /* Ensure it stays above everything */
}

/* --- RESET LIST SPACING --- */
:deep(.p-menu-list) {
  padding: 0;
  margin: 0;
  list-style-type: none;
}

/* --- MENU ITEMS --- */
:deep(.p-menuitem) {
  margin: 0.15rem 0; /* Tiny gap between items */
}

:deep(.p-menuitem-link) {
  color: var(--text-strong) !important;
  font-weight: 500;
  padding: 0.5rem 0.75rem; /* Consistent internal spacing */
  transition: background 0.2s, color 0.2s;
  border-radius: 6px; /* Keep hover background inside the container */
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 0.75rem; /* Space between icon and text */
}

:deep(.p-menuitem-link:hover) {
  background: var(--surface-soft) !important;
  color: var(--text-strong) !important;
}

/* --- MENU SEPARATOR --- */
:deep(.p-menu-separator) {
  border-top: 1px solid var(--border-color);
  margin: 0.5rem 0;
}
</style>
