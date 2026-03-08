<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useWalletStore } from "@/stores/wallet";
import { useSubscriptionStore } from "@/stores/subscription";
import { useAuthStore } from "@/stores/auth";
import { getExplorerTxUrl } from "@/utils/explorer";

const wallet = useWalletStore();
const subscription = useSubscriptionStore();

const auth = useAuthStore();
const message = ref("");
const errorMessage = ref("");
const pendingRefreshing = ref(false);
const approvingId = ref<number | null>(null);
const cancellingId = ref<number | null>(null);
const sortKey = ref<"id" | "vendor_tx_id" | "status" | "request_status" | "amount_xrp" | "escrow_status">("id");
const sortDir = ref<"asc" | "desc">("desc");

function setError(err: any, fallback: string) {
  errorMessage.value = err?.response?.data?.detail || fallback;
  message.value = "";
}

function formatStatusLabel(value: string): string {
  return String(value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function vendorLabel(row: any): string {
  const name = String(row?.vendor_name || "").trim();
  if (name) return name;
  const walletAddress = String(row?.merchant_wallet_address || "").trim();
  if (walletAddress) return `${walletAddress.slice(0, 6)}...${walletAddress.slice(-4)}`;
  return "Vendor";
}

function vendorInitial(row: any): string {
  const label = vendorLabel(row);
  return label.charAt(0).toUpperCase();
}

function shortAddress(value: string): string {
  if (!value) return "-";
  return `${value.slice(0, 6)}...${value.slice(-4)}`;
}

function intervalLabel(row: any): string {
  const seconds = Number(row?.interval_seconds || 0);
  if (Number.isFinite(seconds) && seconds >= 5 && seconds < 86400) {
    if (seconds % 3600 === 0) return `Every ${seconds / 3600} hour${seconds / 3600 === 1 ? "" : "s"}`;
    if (seconds % 60 === 0) return `Every ${seconds / 60} minute${seconds / 60 === 1 ? "" : "s"}`;
    return `Every ${seconds} second${seconds === 1 ? "" : "s"}`;
  }
  return `Every ${row.interval_days} day${row.interval_days !== 1 ? "s" : ""}`;
}

function statusTone(value: string): string {
  const v = String(value || "").toLowerCase();
  if (["active", "approved", "validated", "success", "locked"].includes(v)) return "is-good";
  if (["pending", "queued", "processing", "not_started"].includes(v)) return "is-warn";
  if (["cancelled", "canceled", "failed", "error", "rejected", "expired"].includes(v)) return "is-bad";
  return "is-neutral";
}

const sortedCurrentSubscriptions = computed(() => {
  const rows = [...subscription.list];
  const key = sortKey.value;
  const direction = sortDir.value === "asc" ? 1 : -1;
  return rows.sort((a: any, b: any) => {
    if (key === "id") return (Number(a.id) - Number(b.id)) * direction;
    if (key === "amount_xrp") return (Number(a.amount_xrp) - Number(b.amount_xrp)) * direction;
    const aValue = String(a[key] ?? "").toLowerCase();
    const bValue = String(b[key] ?? "").toLowerCase();
    if (aValue < bValue) return -1 * direction;
    if (aValue > bValue) return 1 * direction;
    return 0;
  });
});

function setSort(
  key: "id" | "vendor_tx_id" | "status" | "request_status" | "amount_xrp" | "escrow_status",
) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === "asc" ? "desc" : "asc";
    return;
  }
  sortKey.value = key;
  sortDir.value = key === "id" ? "desc" : "asc";
}

function sortIndicator(
  key: "id" | "vendor_tx_id" | "status" | "request_status" | "amount_xrp" | "escrow_status",
): string {
  if (sortKey.value !== key) return "";
  return sortDir.value === "asc" ? " ▲" : " ▼";
}

async function refreshSubscriptions() {
  if (!wallet.selectedWallet) return;
  try {
	await subscription.loadAllForWallet(wallet.selectedWallet.address);
  } catch {
	// handled in store
  }
}

async function refreshPending() {
  const resolvedUsername = (auth.username || localStorage.getItem("username") || "").trim();
  if (!resolvedUsername) {
    subscription.pending = [];
    return;
  }
  pendingRefreshing.value = true;
  try {
	await subscription.loadPending(resolvedUsername);
	errorMessage.value = "";
  } catch (err: any) {
	setError(err, "Failed to load pending requests.");
  } finally {
    pendingRefreshing.value = false;
  }
}

async function approveRequest(subscriptionId: number) {
  if (!wallet.selectedWallet) {
    setError(null, "Connect a wallet before approving.");
    return;
  }
  const pendingRow = subscription.pending.find((row: any) => Number(row.id) === Number(subscriptionId));
  const vendorName = pendingRow ? vendorLabel(pendingRow) : `#${subscriptionId}`;
  try {
    approvingId.value = subscriptionId;
    message.value = `Approving ${vendorName} subscription...`;
    errorMessage.value = "";
    await subscription.approve(subscriptionId);
    await refreshPending();
    await refreshSubscriptions();
    message.value = `${vendorName} subscription approved.`;
    errorMessage.value = "";
  } catch (err: any) {
    setError(err, "Failed to approve subscription.");
  } finally {
    approvingId.value = null;
  }
}
async function cancelSubscription(subscriptionId: number) {
  try {
    cancellingId.value = subscriptionId;
    message.value = `Cancelling subscription #${subscriptionId}...`;
    errorMessage.value = "";
    await subscription.cancel(subscriptionId);
    await refreshPending();
    await refreshSubscriptions();
    message.value = `Subscription #${subscriptionId} cancelled.`;
    errorMessage.value = "";
  } catch (err: any) {
    setError(err, "Failed to cancel subscription.");
  } finally {
    cancellingId.value = null;
  }
}
onMounted(async () => {
  await refreshSubscriptions();
  await refreshPending();
});
watch(() => wallet.selectedWallet?.address, async () => {
  await refreshSubscriptions();
  await refreshPending();
});
watch(() => auth.username, async (newUsername) => {
  await refreshPending();
});

async function copyText(value: string) {
  if (!value) return;
  try {
    await navigator.clipboard.writeText(value);
    message.value = "Copied to clipboard.";
    errorMessage.value = "";
  } catch {
    setError(null, "Failed to copy to clipboard.");
  }
}

function explorerTxUrl(txHash: string): string {
  return getExplorerTxUrl(txHash);
}

</script>

<template>
	<section class="stack">
		<article class="panel">
			<h3>Manage Subscriptions</h3>
			<p>Connected wallet: <strong>{{ wallet.selectedWallet?.address || "No wallet selected" }}</strong></p>
		</article>

		<article class="panel">
      <div class="panel-head">
			  <h3>Pending Approvals</h3>
        <button class="compact secondary refresh-btn" :disabled="pendingRefreshing" @click="refreshPending">
          <i class="pi pi-refresh" :class="{ spinning: pendingRefreshing }"></i>
          <span>Refresh</span>
        </button>
      </div>
			<div class="table-wrap">
				<table>
					<thead>
						<tr>
							<th>ID</th>
							<th>Vendor</th>
							<th>Reference ID</th>
              <th>Vendor Wallet</th>
							<th>Amount</th>
							<th>Billing Cycle</th>
							<th>Status</th>
							<th>Actions</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="s in subscription.pending" :key="s.id">
							<td>#{{ s.id }}</td>
              <td>
                <div class="vendor-cell">
                  <img v-if="s.vendor_photo_url" :src="s.vendor_photo_url" class="vendor-avatar" alt="Vendor" />
                  <div v-else class="vendor-avatar fallback">{{ vendorInitial(s) }}</div>
                  <span class="vendor-name">{{ vendorLabel(s) }}</span>
                </div>
              </td>
							<td>{{ s.vendor_tx_id }}</td>
              <td>
                <div class="tx-box wallet-box">
                  <input :value="shortAddress(s.merchant_wallet_address)" readonly />
                  <button
                    class="compact ghost icon-btn"
                    title="Copy wallet address"
                    aria-label="Copy wallet address"
                    @click="copyText(s.merchant_wallet_address)"
                  >
                    <i class="pi pi-copy copy-icon"></i>
                  </button>
                </div>
              </td>
							<td>{{ s.amount_xrp }} RLUSD</td>
							<td>{{ intervalLabel(s) }}</td>
							<td><span class="status-pill" :class="statusTone(s.request_status)">{{ formatStatusLabel(s.request_status) }}</span></td>
							<td class="actions">
								<button class="compact" :disabled="approvingId === s.id" @click="approveRequest(s.id)">
                  {{ approvingId === s.id ? "Approving..." : "Approve" }}
                </button>
								<button class="compact danger" :disabled="cancellingId === s.id" @click="cancelSubscription(s.id)">
                  {{ cancellingId === s.id ? "Cancelling..." : "Cancel" }}
                </button>
							</td>
						</tr>
						<tr v-if="subscription.pending.length === 0">
							<td colspan="8">No plans waiting for approval.</td>
						</tr>
					</tbody>
				</table>
			</div>
		</article>

		<article class="panel">
      <div class="panel-head">
			  <h3>Current Subscriptions</h3>
        <button class="compact secondary" @click="refreshSubscriptions">Refresh</button>
      </div>
			<div class="table-wrap">
				<table>
					<thead>
						<tr>
							<th><button class="th-sort" @click="setSort('id')">ID{{ sortIndicator("id") }}</button></th>
              <th>Vendor</th>
							<th><button class="th-sort" @click="setSort('vendor_tx_id')">Reference ID{{ sortIndicator("vendor_tx_id") }}</button></th>
							<th><button class="th-sort" @click="setSort('status')">Status{{ sortIndicator("status") }}</button></th>
							<th><button class="th-sort" @click="setSort('request_status')">Approval{{ sortIndicator("request_status") }}</button></th>
							<th><button class="th-sort" @click="setSort('amount_xrp')">Amount{{ sortIndicator("amount_xrp") }}</button></th>
							<th><button class="th-sort" @click="setSort('escrow_status')">Escrow State{{ sortIndicator("escrow_status") }}</button></th>
							<th>Last Transaction</th>
							<th>Actions</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="s in sortedCurrentSubscriptions" :key="s.id">
							<td>#{{ s.id }}</td>
              <td>
                <div class="vendor-cell">
                  <img v-if="s.vendor_photo_url" :src="s.vendor_photo_url" class="vendor-avatar" alt="Vendor" />
                  <div v-else class="vendor-avatar fallback">{{ vendorInitial(s) }}</div>
                  <span class="vendor-name">{{ vendorLabel(s) }}</span>
                </div>
              </td>
							<td>{{ s.vendor_tx_id }}</td>
							<td><span class="status-pill" :class="statusTone(s.status)">{{ formatStatusLabel(s.status) }}</span></td>
							<td><span class="status-pill" :class="statusTone(s.request_status)">{{ formatStatusLabel(s.request_status) }}</span></td>
							<td>{{ s.amount_xrp }} RLUSD</td>
							<td><span class="status-pill" :class="statusTone(s.escrow_status)">{{ formatStatusLabel(s.escrow_status) }}</span></td>
							<td>
								<div v-if="s.last_tx_hash" class="tx-box">
									<input :value="s.last_tx_hash" readonly />
									<button
                    class="compact ghost icon-btn"
                    title="Copy transaction hash"
                    aria-label="Copy transaction hash"
                    @click="copyText(s.last_tx_hash)"
                  >
                    <i class="pi pi-copy copy-icon"></i>
                  </button>
                  <a
                    class="compact ghost link-btn icon-btn"
                    :href="explorerTxUrl(s.last_tx_hash)"
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
							<td class="actions">
								<button class="compact danger" :disabled="cancellingId === s.id" @click="cancelSubscription(s.id)">
                  {{ cancellingId === s.id ? "Cancelling..." : "Cancel" }}
                </button>
							</td>
						</tr>
						<tr v-if="subscription.list.length === 0">
							<td colspan="9">No active plans for this wallet yet.</td>
						</tr>
					</tbody>
				</table>
			</div>
		</article>

		<p v-if="message" class="message success">{{ message }}</p>
		<p v-if="errorMessage" class="message error">{{ errorMessage }}</p>
	</section>
</template>

<style scoped>
.stack { display: grid; gap: 1rem; }
.panel {
	background: var(--surface-panel);
	border: 1px solid var(--border-color);
	border-radius: 14px;
	padding: 1rem;
}
h3 { margin: 0 0 0.7rem; color: var(--text-strong); }
label { display: block; color: var(--text-muted); font-size: 0.86rem; margin-bottom: 0.2rem; }
input {
	width: 100%;
	border: 1px solid var(--border-color);
	border-radius: 8px;
	padding: 0.5rem 0.65rem;
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.65rem;
}
.compact {
	border: none;
	border-radius: 8px;
	padding: 0.38rem 0.62rem;
	background: linear-gradient(130deg, var(--accent-1), var(--accent-2));
	color: #fff;
	font-weight: 700;
	font-size: 0.86rem;
	cursor: pointer;
}
.compact:disabled {
  cursor: not-allowed;
  opacity: 0.72;
}
.compact.secondary { background: var(--accent-2); }
.refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}
.refresh-btn i {
  font-size: 0.82rem;
}
.refresh-btn i.spinning {
  animation: spin 0.9s linear infinite;
}
.compact.danger { background: var(--danger-bg); color: var(--btn-text); }
.compact.danger-outline {
	background: var(--danger-bg-soft);
	color: var(--danger-text);
	border: 1px solid var(--danger-bg);
}
.compact.ghost {
	background: var(--surface-soft);
	color: var(--text-muted);
	border: 1px solid var(--border-color);
}
.compact.link-btn {
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  background: color-mix(in srgb, var(--accent-1) 14%, var(--surface-panel));
  color: var(--accent-1);
  border-color: color-mix(in srgb, var(--accent-1) 30%, var(--border-color));
}
.compact.icon-btn {
  width: 28px;
  height: 28px;
  padding: 0;
  justify-content: center;
}
.compact.icon-btn i { font-size: 0.72rem; }
.compact.icon-btn i.copy-icon { font-size: 0.82rem; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; min-width: 900px; }
th, td {
	border-bottom: 1px solid var(--border-color);
	padding: 0.45rem;
	text-align: left;
	color: var(--text-primary);
	font-size: 0.9rem;
}
.th-sort {
  border: none;
  background: transparent;
  color: inherit;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
  padding: 0;
}
.actions { display: flex; gap: 0.35rem; flex-wrap: wrap; }
.vendor-cell {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}
.vendor-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  object-fit: cover;
  border: 1px solid var(--border-color);
}
.vendor-avatar.fallback {
  display: inline-grid;
  place-items: center;
  background: var(--surface-active);
  color: var(--text-strong);
  font-weight: 700;
}
.vendor-name {
  color: var(--text-primary);
  font-weight: 600;
}
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
.tx-box {
	display: inline-flex;
	align-items: center;
	gap: 0.35rem;
	max-width: 280px;
}
.tx-box input {
	width: 210px;
	max-width: 210px;
	padding: 0.28rem 0.45rem;
	border-radius: 6px;
	border: 1px solid var(--border-color);
	background: var(--surface-soft);
	color: var(--text-primary);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}
.message { margin: 0; font-weight: 600; }
.message.success { color: #1f7a3b; }
.message.error { color: #b42318; }
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
@media (max-width: 900px) {
	.filters { grid-template-columns: 1fr; }
}
</style>
