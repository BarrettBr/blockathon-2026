<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
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

onMounted(async () => {
  if (!wallet.aggregateBalance) {
    await wallet.fetchAggregateBalance();
  }
});

watch(
  () => wallet.wallets.length,
  async () => {
    await wallet.fetchAggregateBalance();
  },
);
</script>

<template>
  <header class="topbar">
    <button class="menu-btn" @click="layout.toggleSidebar">☰</button>
    <div class="title">EquiPay: Consumer Payments on XRPL</div>

	<div class="right">
		<div class="balance">Balance: {{ walletBalance }} RLUSD</div>

		<Button 
			 text 
			 class="account-btn"
			 @click="toggleMenu" 
			 >
			 <i class="pi pi-user-circle" style="font-size: 1.5rem; margin-right: 0.5rem;"></i>
			 <span>My Account</span>
			 <i class="pi pi-chevron-down" style="margin-left: 0.5rem; font-size: 0.8rem;"></i>
		</Button>

		<Menu ref="menu" :model="items" :popup="true" />
	</div>
  </header>
</template>

<style scoped>
.account-btn {
  color: #345f94 !important;
  font-weight: 600 !important;
  padding: 0.5rem 0.75rem !important;
}

.account-btn:hover {
  background: #ebf3ff !important;
}

.topbar {
  height: 68px;
  border-bottom: 1px solid #d8e6ff;
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0 1.25rem;
  background: rgba(255, 255, 255, 0.96);
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


/* --- POPUP MENU CONTAINER --- */
:deep(.p-menu) {
  background: #ffffff; /* Fix: Added missing background */
  min-width: 200px;
  border: 1px solid #d8e6ff;
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
  color: #345f94 !important;
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
  background: #f0f7ff !important;
  color: #1f4f90 !important;
}

/* --- MENU SEPARATOR --- */
:deep(.p-menu-separator) {
  border-top: 1px solid #d8e6ff;
  margin: 0.5rem 0;
}
</style>
