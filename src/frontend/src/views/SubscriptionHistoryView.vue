<script setup lang="ts">
import { onMounted, watch } from "vue";
import { useWalletStore } from "@/stores/wallet";
import { useSubscriptionStore } from "@/stores/subscription";
import { getExplorerTxUrl } from "@/utils/explorer";

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

function statusTone(value: string): string {
  const v = String(value || "").toLowerCase();
  if (["active", "approved", "validated", "success", "locked"].includes(v)) return "is-good";
  if (["pending", "queued", "processing", "not_started"].includes(v)) return "is-warn";
  if (["cancelled", "canceled", "failed", "error", "rejected", "expired"].includes(v)) return "is-bad";
  return "is-neutral";
}

async function copyText(value: string) {
  if (!value) return;
  await navigator.clipboard.writeText(value);
}

function explorerTxUrl(txHash: string): string {
  return getExplorerTxUrl(txHash);
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
            <td><span class="status-pill" :class="statusTone(row.status)">{{ row.status }}</span></td>
            <td>{{ row.counterparty_address || "-" }}</td>
            <td>
              <div v-if="row.tx_hash" class="tx-box">
                <input :value="row.tx_hash" readonly />
                <button class="copy-btn icon-btn" title="Copy transaction hash" aria-label="Copy transaction hash" @click="copyText(row.tx_hash)">
                  <i class="pi pi-copy copy-icon"></i>
                </button>
                <a
                  class="copy-btn view-btn icon-btn"
                  :href="explorerTxUrl(row.tx_hash)"
                  target="_blank"
                  rel="noopener noreferrer"
                  title="Open on explorer"
                  aria-label="Open on explorer"
                >
                  <i class="pi pi-external-link"></i>
                </a>
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
  background: var(--surface-panel);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  padding: 1rem;
}
h3 { margin: 0 0 0.7rem; color: var(--text-strong); }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; min-width: 820px; }
th, td {
  border-bottom: 1px solid var(--border-color);
  padding: 0.45rem;
  text-align: left;
  color: var(--text-primary);
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
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--surface-soft);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.copy-btn {
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--surface-soft);
  color: var(--text-muted);
  padding: 0.22rem 0.42rem;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
}
.view-btn {
  background: color-mix(in srgb, var(--accent-1) 14%, var(--surface-panel));
  color: var(--accent-1);
  border-color: color-mix(in srgb, var(--accent-1) 30%, var(--border-color));
}
.icon-btn {
  width: 28px;
  height: 28px;
  padding: 0;
  justify-content: center;
}
.icon-btn i { font-size: 0.72rem; }
.icon-btn i.copy-icon { font-size: 0.82rem; }
.event-pill,
.status-pill {
  display: inline-block;
  border: 1px solid var(--border-color);
  background: var(--surface-soft);
  border-radius: 999px;
  padding: 0.16rem 0.5rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-muted);
}
.status-pill.is-good {
  background: color-mix(in srgb, #22c55e 10%, var(--surface-panel));
  border-color: color-mix(in srgb, #22c55e 22%, var(--border-color));
  color: var(--text-primary);
}
.status-pill.is-warn {
  background: color-mix(in srgb, #f59e0b 10%, var(--surface-panel));
  border-color: color-mix(in srgb, #f59e0b 22%, var(--border-color));
  color: var(--text-primary);
}
.status-pill.is-bad {
  background: color-mix(in srgb, #ef4444 10%, var(--surface-panel));
  border-color: color-mix(in srgb, #ef4444 22%, var(--border-color));
  color: var(--text-primary);
}
</style>
