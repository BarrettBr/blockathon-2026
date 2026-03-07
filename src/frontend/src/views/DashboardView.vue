<script setup lang="ts">
import { computed, onMounted, watch } from "vue";
import { useWalletStore } from "@/stores/wallet";
import { useDashboardStore } from "@/stores/dashboard";

const wallet = useWalletStore();
const dashboard = useDashboardStore();

const data = computed(() => dashboard.data);

async function load() {
  if (!wallet.selectedWallet) return;
  await wallet.fetchSelectedBalance();
  await dashboard.loadDashboard(wallet.selectedWallet.address);
}

onMounted(load);
watch(
  () => wallet.selectedWallet?.address,
  async () => {
    await load();
  },
);
</script>

<template>
  <section class="stack">
    <div class="cards" v-if="data">
      <article class="card"><h4>Balance</h4><p>{{ data.balance_rlusd?.toFixed?.(2) ?? data.balance_rlusd }} RLUSD</p></article>
      <article class="card"><h4>Locked In Escrow</h4><p>{{ data.locked_in_escrow_xrp?.toFixed?.(2) ?? data.locked_in_escrow_xrp }} XRP</p></article>
      <article class="card"><h4>Monthly Guard</h4><p>{{ data.monthly_guard?.limit ?? 0 }} {{ data.monthly_guard?.currency ?? "RLUSD" }}</p></article>
    </div>

    <div class="panel" v-if="data">
      <h3>This Month</h3>
      <div class="month-grid">
        <div>Released: <strong>{{ data.this_month?.released ?? 0 }}</strong></div>
        <div>Locked: <strong>{{ data.this_month?.locked ?? 0 }}</strong></div>
        <div>Remaining Guard: <strong>{{ data.monthly_guard?.remaining ?? 0 }}</strong></div>
      </div>
    </div>

    <div class="split" v-if="data">
      <div class="panel">
        <h3>Upcoming Release</h3>
        <ul>
          <li v-for="item in data.upcoming_release" :key="item.subscription_id">
            #{{ item.subscription_id }} • {{ item.amount_xrp }} XRP • {{ item.next_payment_date }}
          </li>
          <li v-if="!data.upcoming_release?.length">No upcoming releases</li>
        </ul>
      </div>

      <div class="panel">
        <h3>Recent Activity</h3>
        <ul>
          <li v-for="item in data.recent_activity" :key="item.tx_hash + item.created_at">
            {{ item.event_type }} • {{ item.amount ?? 0 }} {{ item.currency }} • {{ item.created_at }}
          </li>
          <li v-if="!data.recent_activity?.length">No activity</li>
        </ul>
      </div>
    </div>

    <div v-if="dashboard.error" class="error">{{ dashboard.error }}</div>
  </section>
</template>

<style scoped>
.stack { display: grid; gap: 1rem; }
.cards { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 1rem; }
.card, .panel {
  background: rgba(255,255,255,0.9);
  border: 1px solid #dceaff;
  border-radius: 14px;
  padding: 1rem;
  box-shadow: 0 10px 22px rgba(29, 76, 132, 0.08);
}
.card h4 { margin: 0 0 0.5rem; color: #5a79a4; font-size: 0.9rem; }
.card p { margin: 0; color: #1f467d; font-weight: 800; font-size: 1.35rem; }
.panel h3 { margin: 0 0 0.75rem; color: #1f467d; }
.month-grid { display: grid; gap: 0.5rem; color: #35577f; }
.split { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
ul { margin: 0; padding-left: 1rem; color: #35577f; }
.error { color: #b42318; font-weight: 600; }
@media (max-width: 900px) {
  .cards, .split { grid-template-columns: 1fr; }
}
</style>
