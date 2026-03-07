<script setup lang="ts">
import { onMounted, watch } from "vue";
import { useWalletStore } from "@/stores/wallet";
import { useHistoryStore } from "@/stores/history";

const wallet = useWalletStore();
const history = useHistoryStore();

async function load() {
  if (!wallet.selectedWallet) return;
  await history.load(wallet.selectedWallet.address, 100);
}

onMounted(load);
watch(() => wallet.selectedWallet?.address, load);
</script>

<template>
  <article class="panel">
    <h3>History</h3>
    <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Date</th>
          <th>Type</th>
          <th>Amount</th>
          <th>Currency</th>
          <th>Status</th>
          <th>Tx Hash</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in history.entries" :key="row.id">
          <td>{{ row.created_at }}</td>
          <td>{{ row.event_type }}</td>
          <td>{{ row.amount ?? "-" }}</td>
          <td>{{ row.currency }}</td>
          <td>{{ row.status }}</td>
          <td>{{ row.tx_hash ?? "-" }}</td>
        </tr>
        <tr v-if="history.entries.length === 0">
          <td colspan="6">No history yet</td>
        </tr>
      </tbody>
    </table>
    </div>
  </article>
</template>

<style scoped>
.panel {
  background: rgba(255,255,255,0.96);
  border: 1px solid #dceaff;
  border-radius: 14px;
  padding: 1rem;
}
h3 { margin: 0 0 0.7rem; color: #1f467d; }
table { width: 100%; border-collapse: collapse; }
th, td { border-bottom: 1px solid #e4efff; padding: 0.5rem; text-align: left; color: #35577f; }
.table-wrap { overflow-x: auto; }
table { min-width: 720px; }
</style>
