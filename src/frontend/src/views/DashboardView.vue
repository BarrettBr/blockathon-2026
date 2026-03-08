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
const monthlyLimit = computed(() => {
  const raw = toNumber(data.value?.monthly_guard?.limit);
  return raw > 0 ? raw : 500;
});
const monthlyLocked = computed(() => toNumber(data.value?.this_month?.locked));
const monthlyRemaining = computed(() => toNumber(data.value?.monthly_guard?.remaining));
const monthlySpentGuard = computed(() => toNumber(data.value?.monthly_guard?.spent));
const lockedInEscrow = computed(() => toNumber(data.value?.locked_in_escrow_xrp));

const chartSpent = computed(() => monthlySpentGuard.value);
const chartReserved = computed(() => monthlyLocked.value);
const chartRemaining = computed(() => {
  if (monthlyLimit.value > 0) {
    return Math.max(monthlyLimit.value - chartSpent.value - chartReserved.value, 0);
  }
  return Math.max(monthlyRemaining.value, 0);
});

const pieTotal = computed(() => {
  const total = chartSpent.value + chartReserved.value + chartRemaining.value;
  return total > 0 ? total : 1;
});

const releasedPct = computed(() => Math.max(0, Math.min(100, (chartSpent.value / pieTotal.value) * 100)));
const lockedPct = computed(() => Math.max(0, Math.min(100, (chartReserved.value / pieTotal.value) * 100)));
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

function shortWallet(address: string): string {
  if (!address) return "Unknown";
  return `${address.slice(0, 6)}...${address.slice(-4)}`;
}

function vendorInitial(name: string): string {
  const text = String(name || "").trim();
  if (!text) return "?";
  return text.charAt(0).toUpperCase();
}

const upcomingSubscriptions = computed(() => {
  const rows = Array.isArray(data.value?.upcoming_release) ? data.value.upcoming_release : [];
  return rows.map((row: any) => {
    const name = String(row.vendor_name || "").trim() || shortWallet(String(row.merchant_wallet_address || ""));
    return {
      key: `${row.subscription_id}-${row.next_payment_date}`,
      name,
      initial: vendorInitial(name),
      amountText: `${fmtAmount(toNumber(row.amount_xrp), 2)} XRP`,
      renewalText: formatDateLabel(String(row.next_payment_date || "")),
    };
  });
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
      <p>Go to <strong>Wallet</strong> and connect a wallet to unlock your dashboard.</p>
    </div>

    <div class="panel" v-else-if="dashboard.loading && !data">
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
        <small>Remaining: {{ fmtAmount(chartRemaining, 2) }} {{ data.monthly_guard?.currency ?? "RLUSD" }}</small>
      </article>
    </div>

    <div class="panel month-panel" v-if="data">
      <div class="month-left">
        <div class="donut" :style="donutStyle">
          <div class="donut-inner">
            <div class="donut-title">This Month</div>
            <div class="donut-value">{{ fmtAmount(chartSpent, 2) }}</div>
            <div class="donut-sub">Spent</div>
          </div>
        </div>
      </div>
      <div class="month-right">
        <h3>This Month</h3>
        <div class="legend">
          <div class="legend-item">
            <span class="dot released"></span>
            <span>Spent so far: <strong>{{ fmtAmount(chartSpent, 2) }} {{ data.monthly_guard?.currency ?? "RLUSD" }}</strong></span>
          </div>
          <div class="legend-item">
            <span class="dot locked"></span>
            <span>Reserved for upcoming subscriptions: <strong>{{ fmtAmount(chartReserved, 2) }} {{ data.monthly_guard?.currency ?? "RLUSD" }}</strong></span>
          </div>
          <div class="legend-item">
            <span class="dot remaining"></span>
            <span>Left in monthly limit: <strong>{{ fmtAmount(chartRemaining, 2) }} {{ data.monthly_guard?.currency ?? "RLUSD" }}</strong></span>
          </div>
        </div>
        <p class="note">Your subscriptions and payments are tracked in simple, clear terms.</p>
      </div>
    </div>

    <div class="split" v-if="data">
      <div class="panel list-panel">
        <h3>Upcoming Subscription Charges</h3>
        <ul class="clean-list">
          <li v-for="item in upcomingSubscriptions" :key="item.key" class="row-item">
            <div class="row-main">
              <div class="avatar" aria-hidden="true">{{ item.initial }}</div>
              <div class="name-col">
                <strong class="name">{{ item.name }}</strong>
                <small>Renews {{ item.renewalText }}</small>
              </div>
              <strong>{{ item.amountText }}</strong>
            </div>
          </li>
          <li v-if="!upcomingSubscriptions.length" class="muted">No upcoming charges</li>
        </ul>
        <div class="panel-footer">
          <RouterLink to="/subscriptions/manage" class="view-more">View more</RouterLink>
        </div>
      </div>

      <div class="panel list-panel">
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
        <div class="panel-footer">
          <RouterLink to="/history" class="view-more">View more</RouterLink>
        </div>
      </div>
    </div>

    <div v-if="errorText" class="error">{{ errorText }}</div>
  </section>
</template>

<style scoped>
.stack { display: grid; gap: 1rem; }
.cards { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 1rem; }
.card, .panel {
  background: var(--surface-panel);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  padding: 1rem;
  box-shadow: 0 10px 22px rgba(29, 76, 132, 0.08);
}
.card h4 { margin: 0 0 0.5rem; color: var(--text-muted); font-size: 0.9rem; }
.card p { margin: 0; color: var(--text-strong); font-weight: 800; font-size: 1.35rem; }
.card small { color: var(--text-muted); font-weight: 700; display: block; margin-top: 0.25rem; }
.panel h3 { margin: 0 0 0.75rem; color: var(--text-strong); }
.split { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.error { color: #b42318; font-weight: 600; }
.empty p { margin: 0; color: var(--text-muted); }
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
  background: var(--surface-panel);
  border: 1px solid var(--border-color);
  display: grid;
  place-items: center;
  text-align: center;
}
.donut-title { color: var(--text-muted); font-size: 0.82rem; }
.donut-value { color: var(--text-strong); font-size: 1.35rem; font-weight: 800; line-height: 1.1; }
.donut-sub { color: var(--text-muted); font-size: 0.78rem; }
.legend { display: grid; gap: 0.45rem; margin-bottom: 0.55rem; }
.legend-item { display: flex; align-items: center; gap: 0.45rem; color: var(--text-primary); }
.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}
.dot.released { background: #19a49b; }
.dot.locked { background: #f2ba2f; }
.dot.remaining { background: #4f95eb; }
.note { margin: 0; color: var(--text-muted); font-size: 0.9rem; }
.clean-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0.6rem;
  align-content: start;
}
.row-item {
  border: 1px solid var(--border-color);
  background: var(--surface-soft);
  border-radius: 10px;
  padding: 0.6rem 0.7rem;
  height: fit-content;
}
.row-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.6rem;
}
.row-main {
  display: grid;
  grid-template-columns: 36px 1fr auto;
  align-items: center;
  gap: 0.65rem;
}
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--surface-active);
  color: var(--text-strong);
  font-weight: 800;
  display: grid;
  place-items: center;
  border: 1px solid var(--border-color);
}
.name-col {
  display: grid;
  min-width: 0;
}
.name {
  color: var(--text-strong);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.row-item small { color: var(--text-muted); }
.pill {
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
  background: var(--surface-active);
  color: var(--text-muted);
  font-size: 0.78rem;
  font-weight: 700;
}
.panel-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: auto;
  padding-top: 0.6rem;
}
.view-more {
  text-decoration: none;
  color: var(--accent-1);
  font-weight: 700;
  font-size: 0.85rem;
}
.list-panel {
  display: flex;
  flex-direction: column;
  height: 360px;
  min-height: 360px;
}
.list-panel .clean-list {
  flex: 1;
  overflow-y: auto;
  padding-right: 0.2rem;
}
.list-panel .clean-list::-webkit-scrollbar {
  width: 8px;
}
.list-panel .clean-list::-webkit-scrollbar-thumb {
  background: color-mix(in srgb, var(--accent-1) 28%, transparent);
  border-radius: 999px;
}
.muted { color: var(--text-muted); }
@media (max-width: 900px) {
  .cards, .split { grid-template-columns: 1fr; }
  .month-panel { grid-template-columns: 1fr; }
}
</style>
