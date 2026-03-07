<script setup lang="ts">
import { onMounted, watch } from "vue";
import { useWalletStore } from "@/stores/wallet";
import { useSubscriptionStore } from "@/stores/subscription";

const wallet = useWalletStore();
const subscription = useSubscriptionStore();

async function load() {
  if (!wallet.selectedWallet) return;
  await subscription.loadHistoryForWallet(wallet.selectedWallet.address, 100);
}

onMounted(load);
watch(() => wallet.selectedWallet?.address, load);
</script>

<template>
  <article class="panel">
    <h3>Subscription History</h3>
    <p>Connected wallet: <strong>{{ wallet.selectedWallet?.address || "No wallet selected" }}</strong></p>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Event</th>
            <th>Amount</th>
            <th>Status</th>
            <th>Counterparty</th>
            <th>Tx Hash</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in subscription.history" :key="row.id">
            <td>{{ row.created_at }}</td>
            <td>{{ row.event_type }}</td>
            <td>{{ row.amount ?? "-" }} {{ row.currency }}</td>
            <td>{{ row.status }}</td>
            <td>{{ row.counterparty_address || "-" }}</td>
            <td>{{ row.tx_hash || "-" }}</td>
          </tr>
          <tr v-if="subscription.history.length === 0">
            <td colspan="6">No subscription history yet.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </article>
</template>

<style scoped>
.panel {
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid #dceaff;
  border-radius: 14px;
  padding: 1rem;
}
h3 { margin: 0 0 0.7rem; color: #1f467d; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; min-width: 820px; }
th, td {
  border-bottom: 1px solid #e4efff;
  padding: 0.45rem;
  text-align: left;
  color: #35577f;
}
</style>
