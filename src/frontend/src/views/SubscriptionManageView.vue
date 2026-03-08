<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useWalletStore } from "@/stores/wallet";
import { useSubscriptionStore } from "@/stores/subscription";
import { useAuthStore } from "@/stores/auth";

const wallet = useWalletStore();
const subscription = useSubscriptionStore();

const auth = useAuthStore();
const message = ref("");
const errorMessage = ref("");
const pendingRefreshing = ref(false);
const approvingId = ref<number | null>(null);
const cancellingId = ref<number | null>(null);

function setError(err: any, fallback: string) {
  errorMessage.value = err?.response?.data?.detail || fallback;
  message.value = "";
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
  try {
    approvingId.value = subscriptionId;
    message.value = `Approving subscription #${subscriptionId}...`;
    errorMessage.value = "";
    await subscription.approve(subscriptionId);
    await refreshPending();
    await refreshSubscriptions();
    message.value = `Subscription #${subscriptionId} approved.`;
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

</script>

<template>
	<section class="stack">
		<article class="panel">
			<h3>Manage Subscriptions</h3>
			<p>Connected wallet: <strong>{{ wallet.selectedWallet?.address || "No wallet selected" }}</strong></p>
		</article>

		<article class="panel">
      <div class="panel-head">
			  <h3>Pending Requests</h3>
        <button class="compact secondary" :disabled="pendingRefreshing" @click="refreshPending">
          {{ pendingRefreshing ? "Refreshing..." : "Refresh" }}
        </button>
      </div>
			<div class="table-wrap">
				<table>
					<thead>
						<tr>
							<th>ID</th>
							<th>Vendor Tx</th>
							<th>Amount</th>
							<th>Interval</th>
							<th>Status</th>
							<th>Actions</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="s in subscription.pending" :key="s.id">
							<td>#{{ s.id }}</td>
							<td>{{ s.vendor_tx_id }}</td>
							<td>{{ s.amount_xrp }} XRP</td>
							<td>{{ s.interval_days }}d</td>
							<td>{{ s.request_status }}</td>
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
							<td colspan="6">No pending requests.</td>
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
							<th>ID</th>
							<th>Vendor Tx</th>
							<th>Status</th>
							<th>Request</th>
							<th>Amount</th>
							<th>Escrow</th>
							<th>Last Tx</th>
							<th>Actions</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="s in subscription.list" :key="s.id">
							<td>#{{ s.id }}</td>
							<td>{{ s.vendor_tx_id }}</td>
							<td>{{ s.status }}</td>
							<td>{{ s.request_status }}</td>
							<td>{{ s.amount_xrp }} XRP</td>
							<td>{{ s.escrow_status }}</td>
							<td>
								<div v-if="s.last_tx_hash" class="tx-box">
									<input :value="s.last_tx_hash" readonly />
									<button class="compact ghost" @click="copyText(s.last_tx_hash)">Copy</button>
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
							<td colspan="8">No subscriptions for the connected wallet.</td>
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
	background: rgba(255, 255, 255, 0.96);
	border: 1px solid #dceaff;
	border-radius: 14px;
	padding: 1rem;
}
h3 { margin: 0 0 0.7rem; color: #1f467d; }
label { display: block; color: #47678f; font-size: 0.86rem; margin-bottom: 0.2rem; }
input {
	width: 100%;
	border: 1px solid #cfe0fb;
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
	background: linear-gradient(130deg, #2c6fdf, #1f58bf);
	color: #fff;
	font-weight: 700;
	font-size: 0.86rem;
	cursor: pointer;
}
.compact:disabled {
  cursor: not-allowed;
  opacity: 0.72;
}
.compact.secondary { background: #4f79b8; }
.compact.danger { background: #c37a73; }
.compact.danger-outline {
	background: #f9fbff;
	color: #8d5f5a;
	border: 1px solid #d7b3ae;
}
.compact.ghost {
	background: #eef4ff;
	color: #355a8f;
	border: 1px solid #d6e4fb;
}
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; min-width: 900px; }
th, td {
	border-bottom: 1px solid #e4efff;
	padding: 0.45rem;
	text-align: left;
	color: #35577f;
	font-size: 0.9rem;
}
.actions { display: flex; gap: 0.35rem; flex-wrap: wrap; }
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
	border: 1px solid #d6e4fb;
	background: #f8fbff;
	color: #35577f;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}
.message { margin: 0; font-weight: 600; }
.message.success { color: #1f7a3b; }
.message.error { color: #b42318; }
@media (max-width: 900px) {
	.filters { grid-template-columns: 1fr; }
}
</style>
