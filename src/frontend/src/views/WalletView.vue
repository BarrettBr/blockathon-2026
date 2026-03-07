<script setup lang="ts">
import { computed, ref } from "vue";
import { useWalletStore } from "@/stores/wallet";
import apiHelper from "@/utils/apiHelper";

const wallet = useWalletStore();

const seedInput = ref("");
const destination = ref("");
const xrpAmount = ref(0.1);
const rlusdAmount = ref(1);
const message = ref("");
const loading = ref(false);

const selectedAddress = computed(() => wallet.selectedWallet?.address ?? "");

async function connectWallet() {
  if (!seedInput.value) return;
  loading.value = true;
  message.value = "";
  try {
    await wallet.importWallet(seedInput.value);
    await wallet.fetchSelectedBalance();
    message.value = "Wallet connected";
  } catch {
    message.value = wallet.error || "Failed to connect wallet";
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
      destination_address: destination.value,
      amount_xrp: xrpAmount.value,
    });
    await wallet.fetchSelectedBalance();
    message.value = "XRP payment sent";
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
      destination_address: destination.value,
      amount: rlusdAmount.value,
    });
    await wallet.fetchSelectedBalance();
    message.value = "RLUSD payment sent";
  } catch (error: any) {
    message.value = error?.response?.data?.detail || "Failed to send RLUSD";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <section class="grid">
    <article class="panel">
      <h3>Connect Wallet</h3>
      <label>Existing Wallet Seed</label>
      <input v-model="seedInput" placeholder="sEd..." />
      <button @click="connectWallet" :disabled="loading">Connect</button>

      <div class="meta">Selected: {{ selectedAddress || "None" }}</div>
      <div class="meta" v-if="wallet.balance">XRP: {{ wallet.balance.balance_xrp }}</div>
      <div class="meta" v-if="wallet.balance">RLUSD: {{ wallet.balance.rlusd_balance }}</div>
    </article>

    <article class="panel">
      <h3>Send Money</h3>
      <label>Destination Address</label>
      <input v-model="destination" placeholder="r..." />

      <label>XRP Amount</label>
      <input v-model.number="xrpAmount" type="number" min="0.000001" step="0.000001" />
      <button @click="sendXrp" :disabled="loading || !destination">Send XRP</button>

      <label>RLUSD Amount</label>
      <input v-model.number="rlusdAmount" type="number" min="0.000001" step="0.000001" />
      <button @click="sendRlusd" :disabled="loading || !destination">Send RLUSD</button>

      <p class="message">{{ message }}</p>
    </article>
  </section>
</template>

<style scoped>
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.panel {
  background: rgba(255,255,255,0.9);
  border: 1px solid #dceaff;
  border-radius: 14px;
  padding: 1rem;
  display: grid;
  gap: 0.55rem;
}
h3 { margin: 0 0 0.25rem; color: #1f467d; }
label { color: #597aa6; font-size: 0.88rem; }
input {
  border: 1px solid #cfe0fb;
  border-radius: 10px;
  padding: 0.55rem 0.7rem;
}
button {
  border: none;
  border-radius: 10px;
  padding: 0.6rem 0.8rem;
  background: linear-gradient(130deg, #2c6fdf, #1f58bf);
  color: #fff;
  font-weight: 700;
  cursor: pointer;
}
button:disabled { opacity: 0.5; cursor: not-allowed; }
.meta { color: #456998; font-size: 0.9rem; }
.message { color: #28558e; font-weight: 600; min-height: 1.2rem; }
@media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
</style>
