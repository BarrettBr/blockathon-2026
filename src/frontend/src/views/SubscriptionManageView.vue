<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useWalletStore } from "@/stores/wallet";
import { useSubscriptionStore } from "@/stores/subscription";
import { useAuthStore } from "@/stores/auth";

const wallet = useWalletStore();
const subscription = useSubscriptionStore();

const auth = useAuthStore();
const username = ref(auth.username || "");
const vendorSecret = ref("");
const message = ref("");
const errorMessage = ref("");

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
  if (!username.value) {
	setError(null, "Enter username to load pending requests.");
	return;
  }
  try {
	await subscription.loadPending(username.value);
	message.value = "Pending requests refreshed.";
	errorMessage.value = "";
  } catch (err: any) {
	setError(err, "Failed to load pending requests.");
  }
}

async function approveRequest(subscriptionId: number) {
  if (!wallet.selectedWallet) {
	setError(null, "Connect a wallet before approving.");
	return;
  }
  if (!username.value) {
	setError(null, "Enter username first.");
	return;
  }
  try {
	await subscription.approve(subscriptionId, username.value, wallet.selectedWallet.seed);
	await refreshPending();
	await refreshSubscriptions();
	message.value = `Subscription #${subscriptionId} approved.`;
	errorMessage.value = "";
  } catch (err: any) {
	setError(err, "Failed to approve subscription.");
  }
}

async function cancelAsUser(subscriptionId: number) {
  if (!wallet.selectedWallet || !username.value) {
	setError(null, "Connect wallet and enter username first.");
	return;
  }
  try {
	await subscription.cancelAsUser(subscriptionId, username.value, wallet.selectedWallet.seed);
	await refreshPending();
	await refreshSubscriptions();
	message.value = `Subscription #${subscriptionId} cancelled as user.`;
	errorMessage.value = "";
  } catch (err: any) {
	setError(err, "Failed to cancel subscription as user.");
  }
}

async function cancelAsVendor(subscriptionId: number) {
  if (!vendorSecret.value) {
	setError(null, "Enter vendor shared secret first.");
	return;
  }
  try {
	await subscription.cancelAsVendor(subscriptionId, vendorSecret.value);
	await refreshPending();
	await refreshSubscriptions();
	message.value = `Subscription #${subscriptionId} cancelled as vendor.`;
	errorMessage.value = "";
  } catch (err: any) {
	setError(err, "Failed to cancel subscription as vendor.");
  }
}
watch(() => wallet.selectedWallet?.address, async () => {
  await refreshSubscriptions();
  if (username.value) await subscription.loadPending(username.value);
});

</script>

<template>
	<section class="stack">
		<article class="panel">
			<h3>Manage Subscriptions</h3>
			<p>Connected wallet: <strong>{{ wallet.selectedWallet?.address || "No wallet selected" }}</strong></p>

			<div class="filters">
				<div>
					<label>Username (for pending approvals)</label>
					<input v-model="username" placeholder="alice_subscription_user" />
				</div>
				<div>
					<label>Vendor Shared Secret (optional, for vendor cancel)</label>
					<input v-model="vendorSecret" placeholder="Paste vendor shared secret for vendor-side cancellation" />
				</div>
			</div>

			<div class="actions-row">
				<button class="compact secondary" @click="refreshPending">Load Pending</button>
				<button class="compact secondary" @click="refreshSubscriptions">Refresh Subscriptions</button>
			</div>
		</article>

		<article class="panel">
			<h3>Pending Requests</h3>
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
								<button class="compact" @click="approveRequest(s.id)">Approve</button>
								<button class="compact danger" @click="cancelAsUser(s.id)">Cancel (User)</button>
								<button class="compact danger-outline" @click="cancelAsVendor(s.id)">Cancel (Vendor)</button>
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
			<h3>Current Subscriptions</h3>
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
							<td>{{ s.last_tx_hash || "-" }}</td>
							<td class="actions">
								<button class="compact danger" @click="cancelAsUser(s.id)">Cancel (User)</button>
								<button class="compact danger-outline" @click="cancelAsVendor(s.id)">Cancel (Vendor)</button>
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
.filters {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 0.75rem;
}
.actions-row { display: flex; gap: 0.5rem; margin-top: 0.75rem; }
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
.compact.secondary { background: #4f79b8; }
.compact.danger { background: #b42318; }
.compact.danger-outline {
	background: #fff;
	color: #b42318;
	border: 1px solid #d95d52;
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
.message { margin: 0; font-weight: 600; }
.message.success { color: #1f7a3b; }
.message.error { color: #b42318; }
@media (max-width: 900px) {
	.filters { grid-template-columns: 1fr; }
}
</style>
