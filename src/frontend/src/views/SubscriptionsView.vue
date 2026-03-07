<script setup lang="ts">
import { onMounted, reactive, ref, watch } from "vue";
import { useWalletStore } from "@/stores/wallet";
import { useSubscriptionStore } from "@/stores/subscription";

const wallet = useWalletStore();
const subscription = useSubscriptionStore();

const form = reactive({
  merchant_wallet_address: "",
  amount_xrp: 1,
  interval_days: 30,
  use_escrow: true,
});

const merchantSeed = ref("");
const message = ref("");

async function loadSubscriptions() {
  if (!wallet.selectedWallet) return;
  await subscription.loadForUser(wallet.selectedWallet.address);
}

onMounted(loadSubscriptions);
watch(
  () => wallet.selectedWallet?.address,
  async () => {
    await loadSubscriptions();
  },
);

async function createSubscription() {
  if (!wallet.selectedWallet) return;
  try {
    const row = await subscription.create({
      user_wallet_address: wallet.selectedWallet.address,
      merchant_wallet_address: form.merchant_wallet_address,
      user_seed: wallet.selectedWallet.seed,
      amount_xrp: form.amount_xrp,
      interval_days: form.interval_days,
      use_escrow: form.use_escrow,
    });
    message.value = `Subscription #${row.id} created`;
    await loadSubscriptions();
  } catch (error: any) {
    message.value = error?.response?.data?.detail || "Create failed";
  }
}

async function userApprove(id: number) {
  if (!wallet.selectedWallet) return;
  try {
    await subscription.userApprove(id, wallet.selectedWallet.seed);
    await loadSubscriptions();
  } catch (error: any) {
    message.value = error?.response?.data?.detail || "User approval failed";
  }
}

async function serviceApprove(id: number) {
  try {
    await subscription.serviceApprove(id, merchantSeed.value);
    await loadSubscriptions();
  } catch (error: any) {
    message.value = error?.response?.data?.detail || "Service approval failed";
  }
}

async function processSubscription(id: number, useEscrow: boolean) {
  try {
    await subscription.process(id, useEscrow ? merchantSeed.value : undefined);
    await loadSubscriptions();
  } catch (error: any) {
    message.value = error?.response?.data?.detail || "Process failed";
  }
}

async function cancelSubscription(id: number) {
  try {
    await subscription.cancel(id);
    await loadSubscriptions();
  } catch (error: any) {
    message.value = error?.response?.data?.detail || "Cancel failed";
  }
}
</script>

<template>
  <section class="stack">
    <article class="panel">
      <h3>Create Subscription</h3>
      <p>Connected user: <strong>{{ wallet.selectedWallet?.address || "None" }}</strong></p>

      <label>Merchant Wallet Address</label>
      <input v-model="form.merchant_wallet_address" placeholder="r..." />

      <label>Amount XRP</label>
      <input v-model.number="form.amount_xrp" type="number" min="0.000001" step="0.000001" />

      <label>Interval Days</label>
      <input v-model.number="form.interval_days" type="number" min="1" />

      <label class="checkbox">
        <input v-model="form.use_escrow" type="checkbox" />
        Use Escrow
      </label>

      <button @click="createSubscription">Create</button>
      <p class="message">{{ message }}</p>
    </article>

    <article class="panel">
      <h3>Process/Handshake Merchant Seed</h3>
      <input v-model="merchantSeed" placeholder="sEdMerchant..." />
    </article>

    <article class="panel">
      <h3>Subscriptions</h3>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Status</th>
            <th>Handshake</th>
            <th>Amount</th>
            <th>Escrow</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in subscription.list" :key="s.id">
            <td>#{{ s.id }}</td>
            <td>{{ s.status }}</td>
            <td>{{ s.handshake_status }}</td>
            <td>{{ s.amount_xrp }} XRP</td>
            <td>{{ s.escrow_status }}</td>
            <td class="actions">
              <button @click="userApprove(s.id)">User Approve</button>
              <button @click="serviceApprove(s.id)">Service Approve</button>
              <button @click="processSubscription(s.id, !!s.use_escrow)">Process</button>
              <button class="danger" @click="cancelSubscription(s.id)">Cancel</button>
            </td>
          </tr>
          <tr v-if="subscription.list.length === 0">
            <td colspan="6">No subscriptions yet</td>
          </tr>
        </tbody>
      </table>
    </article>
  </section>
</template>

<style scoped>
.stack { display: grid; gap: 1rem; }
.panel {
  background: rgba(255,255,255,0.9);
  border: 1px solid #dceaff;
  border-radius: 14px;
  padding: 1rem;
}
h3 { margin: 0 0 0.7rem; color: #1f467d; }
label { display: block; color: #597aa6; font-size: 0.88rem; margin-top: 0.5rem; }
input {
  width: 100%;
  border: 1px solid #cfe0fb;
  border-radius: 10px;
  padding: 0.55rem 0.7rem;
}
.checkbox { display: flex; align-items: center; gap: 0.5rem; }
button {
  margin-top: 0.7rem;
  border: none;
  border-radius: 10px;
  padding: 0.45rem 0.6rem;
  background: linear-gradient(130deg, #2c6fdf, #1f58bf);
  color: #fff;
  font-weight: 700;
  cursor: pointer;
}
button.danger { background: #b42318; }
.message { color: #28558e; min-height: 1rem; }
table { width: 100%; border-collapse: collapse; }
th, td { border-bottom: 1px solid #e4efff; padding: 0.5rem; text-align: left; color: #35577f; }
.actions { display: flex; flex-wrap: wrap; gap: 0.35rem; }
.actions button { margin-top: 0; }
</style>
