<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useWalletStore } from "@/stores/wallet";
import apiHelper from "@/utils/apiHelper";

const wallet = useWalletStore();

const seedInput = ref("");
const nicknameInput = ref("");
const destination = ref("");
const xrpAmount = ref(0.1);
const rlusdAmount = ref(1);
const bootstrapAmount = ref(100);
const message = ref("");
const loading = ref(false);

function toNumber(value: unknown): number {
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

const selectedAddress = computed(() => wallet.selectedWallet?.address ?? "");
const selectedNickname = computed(() => wallet.selectedWallet?.nickname ?? "");

const resolvedDestinationAddress = computed(() => {
  const raw = destination.value.trim();
  if (!raw) return "";
  if (raw.startsWith("r")) return raw;
  const byNickname = wallet.wallets.find((w) => w.nickname.toLowerCase() === raw.toLowerCase());
  return byNickname?.address || raw;
});

const xrpDisplay = computed(() => {
  const value = toNumber(wallet.balance?.balance_xrp);
  return value.toFixed(6);
});
const rlusdDisplay = computed(() => {
  const direct = toNumber(wallet.balance?.rlusd_balance);
  if (direct > 0) return direct.toFixed(6);

  const issued = Array.isArray(wallet.balance?.issued_balances) ? wallet.balance.issued_balances : [];
  const fallback = issued
    .filter((row: any) => String(row?.currency || "").toUpperCase() === "RLUSD")
    .reduce((sum: number, row: any) => sum + toNumber(row?.balance), 0);
  return fallback.toFixed(6);
});

const aggregateXrp = computed(() => toNumber(wallet.aggregateBalance?.total_balance_xrp).toFixed(6));
const aggregateRlusd = computed(() => toNumber(wallet.aggregateBalance?.total_balance_rlusd).toFixed(6));

async function connectWallet() {
  if (!seedInput.value.trim() || !nicknameInput.value.trim()) return;
  loading.value = true;
  message.value = "";
  try {
    await wallet.connectWallet(seedInput.value.trim(), nicknameInput.value.trim());
    await wallet.fetchAggregateBalance();
    seedInput.value = "";
    message.value = "Wallet connected successfully.";
  } catch {
    message.value = wallet.error || "Failed to connect wallet";
  } finally {
    loading.value = false;
  }
}

async function removeWallet(linkId: number) {
  loading.value = true;
  message.value = "";
  try {
    await wallet.removeConnectedWallet(linkId);
    await wallet.fetchAggregateBalance();
    message.value = "Connected wallet removed.";
  } catch {
    message.value = wallet.error || "Failed to remove wallet";
  } finally {
    loading.value = false;
  }
}

async function bootstrapRlusd() {
  if (!wallet.selectedWallet) return;
  loading.value = true;
  message.value = "";
  try {
    const res = await apiHelper.bootstrapRlusdWallet({
      user_seed: wallet.selectedWallet.seed,
      mint_amount: bootstrapAmount.value,
    });
    await wallet.fetchSelectedBalance();
    await wallet.fetchAggregateBalance();
    message.value = `RLUSD ready. Mint tx: ${res.data.data.mint_tx_hash}`;
  } catch (error: any) {
    message.value = error?.response?.data?.detail || "RLUSD bootstrap failed";
  } finally {
    loading.value = false;
  }
}

async function sendXrp() {
  if (!wallet.selectedWallet) return;
  loading.value = true;
  message.value = "";
  try {
    await apiHelper.sendXrpPayment({
      sender_seed: wallet.selectedWallet.seed,
      destination_address: resolvedDestinationAddress.value,
      amount_xrp: xrpAmount.value,
    });
    await wallet.fetchSelectedBalance();
    await wallet.fetchAggregateBalance();
    message.value = "XRP payment sent.";
  } catch (error: any) {
    message.value = error?.response?.data?.detail || "Failed to send XRP";
  } finally {
    loading.value = false;
  }
}

async function sendRlusd() {
  if (!wallet.selectedWallet) return;
  loading.value = true;
  message.value = "";
  try {
    await apiHelper.sendRlusdPayment({
      sender_seed: wallet.selectedWallet.seed,
      destination_address: resolvedDestinationAddress.value,
      amount: rlusdAmount.value,
    });
    await wallet.fetchSelectedBalance();
    await wallet.fetchAggregateBalance();
    message.value = "RLUSD payment sent.";
  } catch (error: any) {
    message.value = error?.response?.data?.detail || "Failed to send RLUSD";
  } finally {
    loading.value = false;
  }
}

async function prevPage() {
  if (wallet.page > 1) {
    await wallet.goToPage(wallet.page - 1);
  }
}

async function nextPage() {
  if (wallet.page < wallet.pages) {
    await wallet.goToPage(wallet.page + 1);
  }
}

onMounted(async () => {
  await wallet.loadWallets(1);
  if (wallet.selectedWallet) {
    await wallet.fetchSelectedBalance();
  }
  await wallet.fetchAggregateBalance();
});

watch(
  () => wallet.selectedWallet?.link_id,
  async () => {
    if (wallet.selectedWallet) {
      await wallet.fetchSelectedBalance();
    }
  },
);
</script>

<template>
  <section class="wallet-stack">
    <article class="panel">
      <h3>Connect a Wallet</h3>
      <label>Wallet Seed</label>
      <input v-model="seedInput" placeholder="sEd..." />

      <label>Wallet Shortcut Name</label>
      <input v-model="nicknameInput" placeholder="Main Wallet" />

      <button @click="connectWallet" :disabled="loading">Connect Wallet</button>
    </article>

    <article class="panel">
      <h3>Connected Wallets</h3>
      <p class="meta"><strong>Aggregate:</strong> {{ aggregateXrp }} XRP • {{ aggregateRlusd }} RLUSD</p>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Address</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="w in wallet.wallets" :key="w.link_id">
              <td>{{ w.nickname }}</td>
              <td>{{ w.address }}</td>
              <td class="actions">
                <button class="small" @click="wallet.selectWallet(w.link_id)">Use</button>
                <button class="small danger" @click="removeWallet(w.link_id)">Delete</button>
              </td>
            </tr>
            <tr v-if="wallet.wallets.length === 0">
              <td colspan="3">No connected wallets yet.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="pagination">
        <button class="small" :disabled="wallet.page <= 1" @click="prevPage">Prev</button>
        <span>Page {{ wallet.page }} / {{ wallet.pages || 1 }}</span>
        <button class="small" :disabled="wallet.page >= wallet.pages" @click="nextPage">Next</button>
      </div>
    </article>

    <article class="panel">
      <h3>Selected Wallet</h3>
      <div class="meta"><strong>Name:</strong> {{ selectedNickname || "None" }}</div>
      <div class="meta"><strong>Address:</strong> {{ selectedAddress || "None" }}</div>
      <div class="meta" v-if="wallet.balance"><strong>XRP:</strong> {{ xrpDisplay }}</div>
      <div class="meta" v-if="wallet.balance"><strong>RLUSD:</strong> {{ rlusdDisplay }}</div>
    </article>

    <article class="panel">
      <h3>Prepare RLUSD (Trustline + Mint)</h3>
      <label>Mint Amount</label>
      <input v-model.number="bootstrapAmount" type="number" min="0.000001" step="0.000001" />
      <button @click="bootstrapRlusd" :disabled="loading || !wallet.selectedWallet">Bootstrap RLUSD</button>
    </article>

    <article class="panel">
      <h3>Send Assets</h3>
      <p class="meta">Using wallet: <strong>{{ selectedNickname || "None" }}</strong></p>

      <label>Destination (Wallet Address or Shortcut Name)</label>
      <input v-model="destination" placeholder="r... or Savings Wallet" />
      <p class="hint" v-if="destination">Resolved destination: {{ resolvedDestinationAddress }}</p>

      <div class="row">
        <div class="field">
          <label>XRP Amount</label>
          <input v-model.number="xrpAmount" type="number" min="0.000001" step="0.000001" />
          <button @click="sendXrp" :disabled="loading || !destination || !wallet.selectedWallet">Send XRP</button>
        </div>

        <div class="field">
          <label>RLUSD Amount</label>
          <input v-model.number="rlusdAmount" type="number" min="0.000001" step="0.000001" />
          <button @click="sendRlusd" :disabled="loading || !destination || !wallet.selectedWallet">Send RLUSD</button>
        </div>
      </div>

      <p class="message">{{ message }}</p>
    </article>
  </section>
</template>

<style scoped>
.wallet-stack { display: grid; gap: 1rem; }
.panel {
  background: rgba(255, 255, 255, 0.97);
  border: 1px solid #dceaff;
  border-radius: 14px;
  padding: 1rem;
  display: grid;
  gap: 0.55rem;
  align-content: start;
}
h3 { margin: 0 0 0.25rem; color: #1f467d; }
label { color: #47678f; font-size: 0.88rem; }
input {
  border: 1px solid #cfe0fb;
  border-radius: 10px;
  padding: 0.55rem 0.7rem;
}
button {
  border: none;
  border-radius: 10px;
  padding: 0.55rem 0.85rem;
  background: linear-gradient(130deg, #2c6fdf, #1f58bf);
  color: #fff;
  font-weight: 700;
  cursor: pointer;
  width: fit-content;
}
button:disabled { opacity: 0.5; cursor: not-allowed; }
.small {
  padding: 0.34rem 0.6rem;
  border-radius: 8px;
  background: #5e86bf;
}
.danger { background: #cf6f6a; }
.meta { color: #284a73; font-size: 0.92rem; word-break: break-all; margin: 0; }
.hint { margin: 0; color: #3d6191; font-size: 0.87rem; }
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.field { display: grid; gap: 0.45rem; }
.message { color: #28558e; font-weight: 600; min-height: 1.2rem; margin: 0; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; min-width: 560px; }
th, td { border-bottom: 1px solid #e4efff; padding: 0.45rem; text-align: left; color: #2f4f74; }
.actions { display: flex; gap: 0.45rem; flex-wrap: wrap; }
.pagination { display: flex; gap: 0.75rem; align-items: center; margin-top: 0.5rem; color: #3f628f; }
@media (max-width: 900px) { .row { grid-template-columns: 1fr; } }
</style>
