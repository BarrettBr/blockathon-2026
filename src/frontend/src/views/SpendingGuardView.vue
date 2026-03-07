<script setup lang="ts">
import { onMounted, reactive, watch } from "vue";
import { useWalletStore } from "@/stores/wallet";
import { useSpendingGuardStore } from "@/stores/spendingGuard";

const wallet = useWalletStore();
const guard = useSpendingGuardStore();

const form = reactive({
  monthly_limit: 500,
  currency: "RLUSD",
});

async function load() {
  if (!wallet.selectedWallet) return;
  await guard.load(wallet.selectedWallet.address);
  if (guard.guard) {
    form.monthly_limit = guard.guard.monthly_limit;
    form.currency = guard.guard.currency;
  }
}

onMounted(load);
watch(() => wallet.selectedWallet?.address, load);

async function save() {
  if (!wallet.selectedWallet) return;
  await guard.save({
    user_wallet_address: wallet.selectedWallet.address,
    monthly_limit: form.monthly_limit,
    currency: form.currency,
  });
}
</script>

<template>
  <article class="panel">
    <h3>Spending Guard</h3>

    <label>Currency</label>
    <input v-model="form.currency" />

    <label>Monthly Limit</label>
    <input v-model.number="form.monthly_limit" type="number" min="0" step="0.01" />

    <button @click="save">Save Guard</button>

    <div class="meta" v-if="guard.guard">
      <p>Spent: {{ guard.guard.spent_this_month }}</p>
      <p>Remaining: {{ guard.guard.remaining }}</p>
      <p>Month: {{ guard.guard.month_key }}</p>
    </div>
  </article>
</template>

<style scoped>
.panel {
  background: rgba(255,255,255,0.9);
  border: 1px solid #dceaff;
  border-radius: 14px;
  padding: 1rem;
  display: grid;
  gap: 0.55rem;
}
h3 { margin: 0 0 0.5rem; color: #1f467d; }
label { color: #597aa6; font-size: 0.88rem; }
input { border: 1px solid #cfe0fb; border-radius: 10px; padding: 0.55rem 0.7rem; }
button {
  border: none; border-radius: 10px; padding: 0.6rem 0.8rem;
  background: linear-gradient(130deg, #2c6fdf, #1f58bf); color: #fff; font-weight: 700; cursor: pointer;
}
.meta { color: #35577f; }
</style>
