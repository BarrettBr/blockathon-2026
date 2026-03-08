<script setup lang="ts">
import { computed, watch } from "vue";
import { useWalletStore } from "@/stores/wallet";
import { useDashboardStore } from "@/stores/dashboard";

const wallet = useWalletStore();
const dashboard = useDashboardStore();

const data = computed(() => dashboard.data);
const errorText = computed(() => wallet.error || dashboard.error || "");

function toNumber(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function fmtAmount(value: number, decimals = 2): string {
  return value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function formatDateLabel(value: string): string {
  if (!value) return "-";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function friendlyEventName(eventType: string): string {
  const labels: Record<string, string> = {
    subscription_cycle_escrow_lock: "Subscription Locked",
    subscription_non_renewing: "Auto-Renew Turned Off",
    subscription_request_cancelled: "Subscription Request Canceled",
    payment_sent: "Payment Sent",
    payment_sent_rlusd: "RLUSD Payment Sent",
    rlusd_minted: "RLUSD Added",
  };
  if (labels[eventType]) return labels[eventType];
  return eventType
    .replace(/^subscription_/, "Subscription ")
    .replace(/^payment_/, "Payment ")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

const xrpBalance = computed(() => toNumber(data.value?.balance_xrp));
const rlusdBalance = computed(() => toNumber(data.value?.balance_rlusd));
const monthlyLimit = computed(() => toNumber(data.value?.monthly_guard?.limit));
const monthlyReleased = computed(() => toNumber(data.value?.this_month?.released));
const monthlyLocked = computed(() => toNumber(data.value?.this_month?.locked));
const monthlyRemaining = computed(() => toNumber(data.value?.monthly_guard?.remaining));
const lockedInEscrow = computed(() => toNumber(data.value?.locked_in_escrow_xrp));

const pieTotal = computed(() => {
  const guard = monthlyLimit.value;
  if (guard > 0) return guard;
  const fallback = monthlyReleased.value + monthlyLocked.value + monthlyRemaining.value;
  return fallback > 0 ? fallback : 1;
});

const releasedPct = computed(() => Math.max(0, Math.min(100, (monthlyReleased.value / pieTotal.value) * 100)));
const lockedPct = computed(() => Math.max(0, Math.min(100, (monthlyLocked.value / pieTotal.value) * 100)));
const remainingPct = computed(() => Math.max(0, 100 - releasedPct.value - lockedPct.value));

const donutStyle = computed(() => {
  const r = releasedPct.value;
  const l = lockedPct.value;
  const g = remainingPct.value;
  return {
    background: `conic-gradient(
      #19a49b 0% ${r}%,
      #f2ba2f ${r}% ${r + l}%,
      #4f95eb ${r + l}% ${r + l + g}%,
      #d9e8ff ${r + l + g}% 100%
    )`,
  };
});

const recentActivity = computed(() => {
  const rows = Array.isArray(data.value?.recent_activity) ? data.value.recent_activity : [];
  return rows.map((row: any) => ({
    key: `${row.tx_hash || "no-hash"}-${row.created_at || ""}`,
    label: friendlyEventName(String(row.event_type || "")),
    amountText: `${fmtAmount(toNumber(row.amount || 0))} ${row.currency || "XRP"}`,
    dateText: formatDateLabel(String(row.created_at || "")),
  }));
});

async function load() {
  if (!wallet.wallets.length) {
    dashboard.data = null;
    return;
  }

  try {
    await wallet.fetchAggregateBalance();
    await dashboard.loadDashboard();
  } catch {
    // Store-level errors are surfaced in UI through errorText.
  }
}

watch(
  () => wallet.wallets.length,
  async () => {
    await load();
  },
  { immediate: true },
);
</script>

<template>
  <section class="stack">
    <div class="panel empty" v-if="!wallet.wallets.length && !dashboard.loading">
      <h3>No Connected Wallets</h3>
      <p>Go to <strong>Wallets & Transfers</strong> and connect a wallet to unlock your dashboard.</p>
    </div>

    <div class="panel" v-else-if="dashboard.loading">
      <h3>Loading your dashboard...</h3>
    </div>

    <div class="cards" v-if="data">
      <article class="card">
        <h4>Total Wallet Balance</h4>
        <p>{{ fmtAmount(rlusdBalance, 2) }} RLUSD</p>
        <small>{{ fmtAmount(xrpBalance, 6) }} XRP</small>
      </article>
      <article class="card">
        <h4>Locked in Escrow</h4>
        <p>{{ fmtAmount(lockedInEscrow, 6) }} XRP</p>
      </article>
      <article class="card">
        <h4>Monthly Spending Limit</h4>
        <p>{{ fmtAmount(monthlyLimit, 2) }} {{ data.monthly_guard?.currency ?? "RLUSD" }}</p>
        <small>Remaining: {{ fmtAmount(monthlyRemaining, 2) }} {{ data.monthly_guard?.currency ?? "RLUSD" }}</small>
      </article>
    </div>

    <div class="panel month-panel" v-if="data">
      <div class="month-left">
        <div class="donut" :style="donutStyle">
          <div class="donut-inner">
            <div class="donut-title">This Month</div>
            <div class="donut-value">{{ fmtAmount(monthlyReleased, 2) }}</div>
            <div class="donut-sub">Spent</div>
          </div>
        </div>
      </div>
      <div class="month-right">
        <h3>This Month</h3>
        <div class="legend">
          <div class="legend-item">
            <span class="dot released"></span>
            <span>Spent so far: <strong>{{ fmtAmount(monthlyReleased, 2) }} RLUSD</strong></span>
          </div>
          <div class="legend-item">
            <span class="dot locked"></span>
            <span>Reserved for upcoming subscriptions: <strong>{{ fmtAmount(monthlyLocked, 2) }} RLUSD</strong></span>
          </div>
          <div class="legend-item">
            <span class="dot remaining"></span>
            <span>Left in monthly limit: <strong>{{ fmtAmount(monthlyRemaining, 2) }} RLUSD</strong></span>
          </div>
        </div>
        <p class="note">Your subscriptions and payments are tracked in simple, clear terms.</p>
      </div>
    </div>

    <div class="split" v-if="data">
      <div class="panel">
        <h3>Upcoming Subscription Charges</h3>
        <ul class="clean-list">
          <li v-for="item in data.upcoming_release" :key="item.subscription_id" class="row-item">
            <div class="row-top">
              <span class="pill">Subscription #{{ item.subscription_id }}</span>
              <strong>{{ fmtAmount(toNumber(item.amount_xrp), 2) }} XRP</strong>
            </div>
            <small>Next date: {{ formatDateLabel(item.next_payment_date) }}</small>
          </li>
          <li v-if="!data.upcoming_release?.length" class="muted">No upcoming charges</li>
        </ul>
      </div>

      <div class="panel">
        <h3>Recent Activity</h3>
        <ul class="clean-list">
          <li v-for="item in recentActivity" :key="item.key" class="row-item">
            <div class="row-top">
              <span class="pill">{{ item.label }}</span>
              <strong>{{ item.amountText }}</strong>
            </div>
            <small>{{ item.dateText }}</small>
          </li>
          <li v-if="!recentActivity.length" class="muted">No activity yet</li>
        </ul>
      </div>
    </div>

    <div v-if="errorText" class="error">{{ errorText }}</div>
  </section>
</template>

<style scoped>
.stack { display: grid; gap: 1rem; }
.cards { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 1rem; }
.card, .panel {
  background: rgba(255,255,255,0.96);
  border: 1px solid #dceaff;
  border-radius: 14px;
  padding: 1rem;
  box-shadow: 0 10px 22px rgba(29, 76, 132, 0.08);
}
.card h4 { margin: 0 0 0.5rem; color: #5a79a4; font-size: 0.9rem; }
.card p { margin: 0; color: #1f467d; font-weight: 800; font-size: 1.35rem; }
.card small { color: #4d6f99; font-weight: 700; display: block; margin-top: 0.25rem; }
.panel h3 { margin: 0 0 0.75rem; color: #1f467d; }
.split { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.error { color: #b42318; font-weight: 600; }
.empty p { margin: 0; color: #4b6992; }
.month-panel {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 1rem;
  align-items: center;
}
.donut {
  width: 220px;
  height: 220px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  margin: 0 auto;
}
.donut-inner {
  width: 140px;
  height: 140px;
  border-radius: 50%;
  background: #fff;
  border: 1px solid #dceaff;
  display: grid;
  place-items: center;
  text-align: center;
}
.donut-title { color: #5b79a4; font-size: 0.82rem; }
.donut-value { color: #1f467d; font-size: 1.35rem; font-weight: 800; line-height: 1.1; }
.donut-sub { color: #6b88b1; font-size: 0.78rem; }
.legend { display: grid; gap: 0.45rem; margin-bottom: 0.55rem; }
.legend-item { display: flex; align-items: center; gap: 0.45rem; color: #35577f; }
.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}
.dot.released { background: #19a49b; }
.dot.locked { background: #f2ba2f; }
.dot.remaining { background: #4f95eb; }
.note { margin: 0; color: #57739c; font-size: 0.9rem; }
.clean-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0.6rem;
}
.row-item {
  border: 1px solid #e1ecff;
  background: #f9fbff;
  border-radius: 10px;
  padding: 0.6rem 0.7rem;
}
.row-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.6rem;
}
.row-item small { color: #5f7ea8; }
.pill {
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
  background: #eaf2ff;
  color: #355a8f;
  font-size: 0.78rem;
  font-weight: 700;
}
.muted { color: #6280aa; }
@media (max-width: 900px) {
  .cards, .split { grid-template-columns: 1fr; }
  .month-panel { grid-template-columns: 1fr; }
}
</style>
