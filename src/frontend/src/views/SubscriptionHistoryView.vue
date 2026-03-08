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

function formatEventLabel(eventType: string) {
  if (!eventType) return "-";
  return eventType
    .replace(/^subscription_/, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatDateLabel(value: string): string {
  if (!value) return "-";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

async function copyText(value: string) {
  if (!value) return;
  await navigator.clipboard.writeText(value);
}
</script>

<template>
  <article class="panel">
    <h3>Plan History</h3>
    <p>Connected wallet: <strong>{{ wallet.selectedWallet?.address || "No wallet selected" }}</strong></p>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Activity</th>
            <th>Business</th>
            <th>Amount</th>
            <th>Status</th>
            <th>Counterparty Wallet</th>
            <th>Transaction</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in subscription.history" :key="row.id">
            <td>{{ formatDateLabel(row.created_at) }}</td>
            <td><span class="event-pill">{{ formatEventLabel(row.event_type) }}</span></td>
            <td>{{ row.vendor_name || row.note || "-" }}</td>
            <td>{{ row.amount ?? "-" }} {{ row.currency }}</td>
            <td><span class="status-pill">{{ row.status }}</span></td>
            <td>{{ row.counterparty_address || "-" }}</td>
            <td>
              <div v-if="row.tx_hash" class="tx-box">
                <input :value="row.tx_hash" readonly />
                <button class="copy-btn" @click="copyText(row.tx_hash)">Copy</button>
              </div>
              <span v-else>-</span>
            </td>
          </tr>
          <tr v-if="subscription.history.length === 0">
            <td colspan="7">No subscription history yet.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </article>
</template>

<style scoped>
.panel {
  background: rgba(255, 255, 255, 0.96);
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
.tx-box {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  max-width: 280px;
}
.tx-box input {
  width: 210px;
  max-width: 210px;
  padding: 0.25rem 0.45rem;
  border: 1px solid #d6e4fb;
  border-radius: 6px;
  background: #f8fbff;
  color: #35577f;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.copy-btn {
  border: 1px solid #d6e4fb;
  border-radius: 6px;
  background: #eef4ff;
  color: #355a8f;
  padding: 0.22rem 0.42rem;
  font-weight: 600;
  cursor: pointer;
}
.event-pill,
.status-pill {
  display: inline-block;
  border: 1px solid #d7e5fb;
  background: #f4f8ff;
  border-radius: 999px;
  padding: 0.16rem 0.5rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: #3b5f8f;
}
</style>
