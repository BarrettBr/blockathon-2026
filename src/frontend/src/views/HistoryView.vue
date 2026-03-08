<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useWalletStore } from "@/stores/wallet";
import { useHistoryStore } from "@/stores/history";
import apiHelper from "@/utils/apiHelper";
import { getExplorerTxUrl } from "@/utils/explorer";

const wallet = useWalletStore();
const history = useHistoryStore();

// AI Review state
const showModal = ref(false);
const reviewing = ref(false);
const reviewSummary = ref("");
const reviewError = ref("");
const selectedDays = ref(30);
const selectedWallets = ref<string[]>([]);

async function load() {
  if (!wallet.selectedWallet) return;
  await history.load(wallet.selectedWallet.address, 100);
}

async function openReview() {
  selectedWallets.value = wallet.wallets.map((w) => w.address);
  reviewSummary.value = "";
  reviewError.value = "";
  showModal.value = true;
  await runReview();
}

async function runReview() {
  if (selectedWallets.value.length === 0) {
    reviewError.value = "Select at least one wallet.";
    return;
  }
  reviewing.value = true;
  reviewSummary.value = "";
  reviewError.value = "";
  try {
    const res = await apiHelper.aiReview({
      wallet_addresses: selectedWallets.value,
      days: selectedDays.value,
    });
    reviewSummary.value = res.data.data.summary;
  } catch (err: any) {
    reviewError.value = err?.response?.data?.detail || "AI review failed.";
  } finally {
    reviewing.value = false;
  }
}

onMounted(load);
watch(() => wallet.selectedWallet?.address, load);

function formatEventLabel(eventType: string): string {
  const labels: Record<string, string> = {
    subscription_cycle_escrow_lock: "Subscription Locked",
    subscription_non_renewing: "Auto-Renew Turned Off",
    subscription_request_cancelled: "Subscription Request Canceled",
    payment_sent: "Payment Sent",
    payment_sent_rlusd: "RLUSD Payment Sent",
    rlusd_minted: "RLUSD Added",
  };
  if (labels[eventType]) return labels[eventType];
  return String(eventType || "")
    .replace(/^subscription_/, "Subscription ")
    .replace(/^payment_/, "Payment ")
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

function explorerTxUrl(txHash: string): string {
  return getExplorerTxUrl(txHash);
}
</script>

<template>
  <article class="panel">
    <div class="header-row">
      <h3>History</h3>
      <button @click="openReview" :disabled="!wallet.selectedWallet">
        ✨ AI Review
      </button>
    </div>

    <div class="table-wrap">
      <table>
        <thead>
        <tr>
          <th>Date</th>
          <th>Activity</th>
          <th>Vendor / Service</th>
          <th>Amount</th>
          <th>Status</th>
          <th>Transaction</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in history.entries" :key="row.id">
          <td>{{ formatDateLabel(row.created_at) }}</td>
          <td><span class="event-pill">{{ formatEventLabel(row.event_type) }}</span></td>
          <td>{{ row.vendor_name || row.note || "-" }}</td>
          <td>{{ row.amount ?? "-" }} {{ row.currency }}</td>
          <td><span class="status-pill">{{ row.status }}</span></td>
          <td>
            <div v-if="row.tx_hash" class="tx-box">
              <input :value="row.tx_hash" readonly />
              <button class="copy-btn" @click="copyText(row.tx_hash)">Copy</button>
              <a class="copy-btn view-btn" :href="explorerTxUrl(row.tx_hash)" target="_blank" rel="noopener noreferrer">View</a>
            </div>
            <span v-else>-</span>
          </td>
        </tr>
        <tr v-if="history.entries.length === 0">
          <td colspan="6">No payment or subscription activity yet.</td>
        </tr>
      </tbody>
    </table>
    </div>
  </article>

  <!-- AI Review Modal -->
  <teleport to="body">
    <div
      v-if="showModal"
      class="modal-backdrop"
      @click.self="showModal = false"
    >
      <div class="modal">
        <div class="modal-header">
          <h3>✨ AI Spending Review</h3>
          <button class="close" @click="showModal = false">✕</button>
        </div>

        <div class="modal-controls">
          <div class="control-group">
            <label>Period</label>
            <select v-model="selectedDays">
              <option :value="30">Last 30 days</option>
              <option :value="60">Last 60 days</option>
              <option :value="90">Last 90 days</option>
            </select>
          </div>

          <div class="control-group">
            <label>Wallets to include</label>
            <div class="wallet-checkboxes">
              <label
                v-for="w in wallet.wallets"
                :key="w.address"
                class="checkbox-label"
              >
                <input
                  type="checkbox"
                  :value="w.address"
                  v-model="selectedWallets"
                />
                {{ w.nickname }}
                <span class="addr">{{ w.address.slice(0, 8) }}…</span>
              </label>
            </div>
          </div>

          <button class="refresh-btn" @click="runReview" :disabled="reviewing">
            {{ reviewing ? "Analyzing…" : "Re-run Review" }}
          </button>
        </div>

        <div class="modal-body">
          <div v-if="reviewing" class="loading">
            <div class="spinner" />
            <p>Analyzing your wallet activity…</p>
          </div>
          <div v-else-if="reviewError" class="error">{{ reviewError }}</div>
          <pre v-else-if="reviewSummary" class="summary">{{
            reviewSummary
          }}</pre>
          <p v-else class="empty">No summary yet.</p>
        </div>
      </div>
    </div>
  </teleport>
</template>

<style scoped>
.panel {
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #dceaff;
  border-radius: 14px;
  padding: 1rem;
}
.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.7rem;
}
h3 {
  margin: 0;
  color: #1f467d;
}
button {
  border: none;
  border-radius: 10px;
  padding: 0.45rem 0.85rem;
  background: linear-gradient(130deg, #2c6fdf, #1f58bf);
  color: #fff;
  font-weight: 700;
  cursor: pointer;
  font-size: 0.88rem;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
table {
  width: 100%;
  border-collapse: collapse;
  min-width: 720px;
}
th,
td {
  border-bottom: 1px solid #e4efff;
  padding: 0.5rem;
  text-align: left;
  color: #35577f;
}
.table-wrap {
  overflow-x: auto;
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
  text-decoration: none;
  display: inline-flex;
  align-items: center;
}
.view-btn { background: #f5f8ff; }

/* Modal */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal {
  background: #fff;
  border-radius: 16px;
  width: min(680px, 95vw);
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.18);
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.2rem;
  border-bottom: 1px solid #e4efff;
}
.modal-header h3 {
  margin: 0;
  color: #1f467d;
}
.close {
  background: none;
  border: none;
  font-size: 1.1rem;
  color: #7090b0;
  cursor: pointer;
  padding: 0.2rem 0.4rem;
}
.modal-controls {
  padding: 0.9rem 1.2rem;
  border-bottom: 1px solid #e4efff;
  display: flex;
  gap: 1rem;
  align-items: flex-end;
  flex-wrap: wrap;
}
.control-group {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.control-group label {
  font-size: 0.83rem;
  color: #47678f;
}
select {
  border: 1px solid #cfe0fb;
  border-radius: 8px;
  padding: 0.4rem 0.6rem;
  color: #2f4f74;
}
.wallet-checkboxes {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.88rem;
  color: #2f4f74;
  cursor: pointer;
}
.addr {
  color: #8aa8cc;
  font-size: 0.8rem;
}
.refresh-btn {
  align-self: flex-end;
}
.modal-body {
  padding: 1.2rem;
  overflow-y: auto;
  flex: 1;
}
.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.8rem;
  padding: 2rem;
  color: #47678f;
}
.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #dceaff;
  border-top-color: #2c6fdf;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.summary {
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 0.92rem;
  color: #2f4f74;
  line-height: 1.6;
  margin: 0;
}
.error {
  color: #b42318;
  font-weight: 600;
}
.empty {
  color: #8aa8cc;
}
</style>
