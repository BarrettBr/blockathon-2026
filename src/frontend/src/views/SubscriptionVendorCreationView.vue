<script setup lang="ts">
import { reactive, ref } from "vue";
import { useSubscriptionStore } from "@/stores/subscription";

const subscription = useSubscriptionStore();

const form = reactive({
  vendor_code: "",
  display_name: "",
  wallet_address: "",
  webhook_url: "",
});

const vendorSecret = ref("");
const message = ref("");
const errorMessage = ref("");

function setError(err: any, fallback: string) {
  errorMessage.value = err?.response?.data?.detail || fallback;
  message.value = "";
}

async function saveVendor() {
  if (!form.vendor_code || !form.display_name || !form.wallet_address) {
    setError(null, "Vendor code, display name, and wallet address are required.");
    return;
  }
  try {
    const result = await subscription.saveVendor({
      vendor_code: form.vendor_code,
      display_name: form.display_name,
      wallet_address: form.wallet_address,
      webhook_url: form.webhook_url || undefined,
      shared_secret: vendorSecret.value || undefined,
    });
    vendorSecret.value = result.shared_secret;
    message.value = "Vendor saved. Keep this shared secret secure.";
    errorMessage.value = "";
  } catch (err: any) {
    setError(err, "Failed to save vendor.");
  }
}

async function loadVendor() {
  if (!vendorSecret.value) {
    setError(null, "Enter shared secret first.");
    return;
  }
  try {
    const result = await subscription.loadVendorMe(vendorSecret.value);
    form.vendor_code = result.vendor_code;
    form.display_name = result.display_name;
    form.wallet_address = result.wallet_address;
    form.webhook_url = result.webhook_url || "";
    message.value = `Loaded vendor profile: ${result.vendor_code}`;
    errorMessage.value = "";
  } catch (err: any) {
    setError(err, "Failed to load vendor profile.");
  }
}

async function updateVendor() {
  if (!vendorSecret.value) {
    setError(null, "Enter shared secret first.");
    return;
  }
  try {
    await subscription.updateVendorMe(vendorSecret.value, {
      display_name: form.display_name,
      wallet_address: form.wallet_address,
      webhook_url: form.webhook_url || undefined,
    });
    message.value = "Vendor profile updated.";
    errorMessage.value = "";
  } catch (err: any) {
    setError(err, "Failed to update vendor profile.");
  }
}

async function regenerateSecret() {
  if (!vendorSecret.value) {
    setError(null, "Enter current shared secret first.");
    return;
  }
  try {
    const result = await subscription.regenerateVendorSecret(vendorSecret.value);
    vendorSecret.value = result.shared_secret;
    message.value = "Shared secret regenerated.";
    errorMessage.value = "";
  } catch (err: any) {
    setError(err, "Failed to regenerate shared secret.");
  }
}
</script>

<template>
  <section class="stack">
    <article class="panel">
      <h3>Business Setup</h3>
      <p class="helper">Set up your business profile so EquiPay can send subscription updates to your backend.</p>

      <label>Business Code</label>
      <input v-model="form.vendor_code" placeholder="spotify_us" />

      <label>Business Name</label>
      <input v-model="form.display_name" placeholder="Spotify US" />

      <label>Payout Wallet Address</label>
      <input v-model="form.wallet_address" placeholder="rPT1Sjq2YGrBMTttX4GZHjKu9dyfzbpAYe" />

      <label>Webhook URL</label>
      <input v-model="form.webhook_url" placeholder="https://vendor.example.com/equipay/webhook" />

      <div class="actions">
        <button class="compact" @click="saveVendor">Save Business</button>
        <button class="compact secondary" @click="updateVendor">Update Business</button>
      </div>

      <label>Shared Secret</label>
      <input
        v-model="vendorSecret"
        placeholder="Paste your full shared secret to load or update this profile"
      />

      <div class="actions">
        <button class="compact secondary" @click="loadVendor">Load Profile</button>
        <button class="compact secondary" @click="regenerateSecret">Regenerate Secret</button>
      </div>

      <p v-if="message" class="message success">{{ message }}</p>
      <p v-if="errorMessage" class="message error">{{ errorMessage }}</p>
    </article>
  </section>
</template>

<style scoped>
.stack { display: grid; gap: 1rem; }
.panel {
  background: var(--surface-panel);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  padding: 1rem;
  width: 100%;
  max-width: 1200px;
}
h3 { margin: 0 0 0.7rem; color: var(--text-strong); }
.helper { margin: 0 0 0.55rem; color: var(--text-muted); }
label { display: block; color: var(--text-muted); font-size: 0.9rem; margin-top: 0.45rem; }
input {
  width: 100%;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 0.5rem 0.65rem;
  margin-top: 0.2rem;
}
.actions { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.75rem; }
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
.compact.secondary { background: var(--accent-2); }
.message { margin: 0.6rem 0 0; font-weight: 600; }
.message.success { color: #1f7a3b; }
.message.error { color: #b42318; }
</style>
