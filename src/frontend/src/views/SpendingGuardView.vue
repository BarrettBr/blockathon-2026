<script setup lang="ts">
import { computed, onMounted, reactive, watch } from "vue";
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
    form.monthly_limit = Number(guard.guard.monthly_limit || 0) > 0 ? guard.guard.monthly_limit : 500;
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

const remaining = computed(() => Number(guard.guard?.remaining || 0));
const limit = computed(() => Number(guard.guard?.monthly_limit || form.monthly_limit || 0));
const progressPct = computed(() => {
  if (limit.value <= 0) return 0;
  const used = limit.value - remaining.value;
  return Math.max(0, Math.min(100, (used / limit.value) * 100));
});
</script>

<template>
  <article class="panel">
    <h3>Monthly Spending Guard</h3>
    <p class="helper">Sets your monthly cap for the selected currency. Tracking updates as outgoing payments are made.</p>

    <label>Currency</label>
    <input v-model="form.currency" />

    <label>Monthly Limit</label>
    <input v-model.number="form.monthly_limit" type="number" min="0" step="0.01" />

    <button @click="save">Save Guard</button>

    <div class="meta" v-if="guard.guard">
      <div class="stats">
        <div class="stat-card">
          <small>Monthly Limit</small>
          <strong>{{ guard.guard.monthly_limit }} {{ guard.guard.currency }}</strong>
        </div>
        <div class="stat-card">
          <small>Spent</small>
          <strong>{{ guard.guard.spent_this_month }} {{ guard.guard.currency }}</strong>
        </div>
        <div class="stat-card">
          <small>Remaining</small>
          <strong>{{ guard.guard.remaining }} {{ guard.guard.currency }}</strong>
        </div>
      </div>
      <div class="progress-wrap">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: `${progressPct}%` }"></div>
        </div>
        <small>{{ progressPct.toFixed(0) }}% used this month ({{ guard.guard.month_key }})</small>
      </div>
    </div>
    <p v-if="guard.error" class="error">{{ guard.error }}</p>
  </article>
</template>

<style scoped>
.panel {
  background: var(--surface-panel);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  padding: 1rem;
  display: grid;
  gap: 0.7rem;
}
h3 { margin: 0 0 0.5rem; color: var(--text-strong); }
.helper { margin: 0; color: var(--text-muted); font-size: 0.88rem; }
label { color: var(--text-muted); font-size: 0.88rem; }
input { border: 1px solid var(--border-color); border-radius: 10px; padding: 0.55rem 0.7rem; }
button {
  border: none; border-radius: 10px; padding: 0.6rem 0.8rem;
  background: linear-gradient(130deg, var(--accent-1), var(--accent-2)); color: #fff; font-weight: 700; cursor: pointer;
}
.meta { color: var(--text-primary); display: grid; gap: 0.55rem; }
.stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.55rem;
}
.stat-card {
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 0.6rem 0.7rem;
  background: var(--surface-soft);
  display: grid;
  gap: 0.15rem;
}
.stat-card small { color: var(--text-muted); font-size: 0.78rem; }
.stat-card strong { color: var(--text-strong); font-size: 0.95rem; }
.progress-wrap {
  display: grid;
  gap: 0.32rem;
}
.progress-wrap small {
  color: var(--text-muted);
  font-size: 0.78rem;
}
.progress-bar {
  height: 10px;
  border-radius: 999px;
  overflow: hidden;
  border: 1px solid var(--border-color);
  background: var(--surface-soft);
}
.progress-fill {
  height: 100%;
  background: linear-gradient(130deg, var(--accent-1), var(--accent-2));
}
.error { margin: 0; color: #b42318; font-weight: 600; }
@media (max-width: 900px) {
  .stats {
    grid-template-columns: 1fr;
  }
}
</style>
