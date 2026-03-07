<script setup lang="ts">
import { computed, ref } from "vue";
import { useWalletStore } from "@/stores/wallet";
import apiHelper from "@/utils/apiHelper";

const wallet = useWalletStore();

const seedInput = ref("");
const destination = ref("");
const xrpAmount = ref(0.1);
const rlusdAmount = ref(1);
const bootstrapAmount = ref(100);
const message = ref("");
const loading = ref(false);

const selectedAddress = computed(() => wallet.selectedWallet?.address ?? "");
const xrpDisplay = computed(() => {
  const value = wallet.balance?.balance_xrp;
  if (typeof value !== "number") return "0.000000";
  return value.toFixed(6);
});
const rlusdDisplay = computed(() => {
  const value = wallet.balance?.rlusd_balance;
  if (typeof value !== "number") return "0";
  return value.toString();
});

async function connectWallet() {
  if (!seedInput.value.trim()) return;
  loading.value = true;
  message.value = "";
  try {
    await wallet.importWallet(seedInput.value.trim());
    await wallet.fetchSelectedBalance();
    message.value = "Wallet connected successfully.";
  } catch {
    message.value = wallet.error || "Failed to connect wallet";
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
      destination_address: destination.value.trim(),
      amount_xrp: xrpAmount.value,
    });
    await wallet.fetchSelectedBalance();
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
      destination_address: destination.value.trim(),
      amount: rlusdAmount.value,
    });
    await wallet.fetchSelectedBalance();
    message.value = "RLUSD payment sent.";
  } catch (error: any) {
    message.value = error?.response?.data?.detail || "Failed to send RLUSD";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <section class="wallet-stack">
    <article class="panel">
      <h3>Connect Existing Wallet</h3>
      <label>Wallet Seed</label>
      <input
        v-model="seedInput"
        placeholder="sEd7xJ9v8mExampleWalletSeedForImportOnly"
      />
      <button @click="connectWallet" :disabled="loading">Connect Wallet</button>

      <div class="meta"><strong>Selected:</strong> {{ selectedAddress || "None" }}</div>
      <div class="meta" v-if="wallet.balance"><strong>XRP:</strong> {{ xrpDisplay }}</div>
      <div class="meta" v-if="wallet.balance"><strong>RLUSD:</strong> {{ rlusdDisplay }}</div>
      <div class="meta" v-if="wallet.balance && !wallet.balance.account_exists">
        Account is not funded on XRPL yet.
      </div>
    </article>

    <article class="panel">
      <h3>Prepare RLUSD (Trustline + Mint)</h3>
      <label>Mint Amount</label>
      <input v-model.number="bootstrapAmount" type="number" min="0.000001" step="0.000001" />
      <button @click="bootstrapRlusd" :disabled="loading || !wallet.selectedWallet">
        Bootstrap RLUSD
      </button>
      <p class="hint">Uses backend issuer config to create trustline and mint RLUSD.</p>
    </article>

    <article class="panel">
      <h3>Send Assets</h3>
      <label>Destination Wallet Address</label>
      <input
        v-model="destination"
        placeholder="rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh"
      />

      <div class="row">
        <div class="field">
          <label>XRP Amount</label>
          <input v-model.number="xrpAmount" type="number" min="0.000001" step="0.000001" />
          <button @click="sendXrp" :disabled="loading || !destination || !wallet.selectedWallet">
            Send XRP
          </button>
        </div>

        <div class="field">
          <label>RLUSD Amount</label>
          <input v-model.number="rlusdAmount" type="number" min="0.000001" step="0.000001" />
          <button @click="sendRlusd" :disabled="loading || !destination || !wallet.selectedWallet">
            Send RLUSD
          </button>
        </div>
      </div>

      <p class="message">{{ message }}</p>
    </article>
  </section>
</template>

<style scoped>
.wallet-stack {
  display: grid;
  gap: 1rem;
}

.panel {
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid #dceaff;
  border-radius: 14px;
  padding: 1rem;
  display: grid;
  gap: 0.55rem;
  align-content: start;
}

h3 {
  margin: 0 0 0.25rem;
  color: #1f467d;
}

label {
  color: #597aa6;
  font-size: 0.88rem;
}

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

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.meta {
  color: #456998;
  font-size: 0.9rem;
  word-break: break-all;
}

.hint {
  margin: 0;
  font-size: 0.82rem;
  color: #6a88b1;
}

.row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.field {
  display: grid;
  gap: 0.45rem;
}

.message {
  color: #28558e;
  font-weight: 600;
  min-height: 1.2rem;
  margin: 0;
}

@media (max-width: 900px) {
  .row {
    grid-template-columns: 1fr;
  }
}
</style>
