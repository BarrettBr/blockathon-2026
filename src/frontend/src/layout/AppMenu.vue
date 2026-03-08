<script setup lang="ts">
import AppMenuItem from "./AppMenuItem.vue";

const items = [
  { label: "Dashboard", to: "/dashboard" },
  { label: "Wallets & Transfers", to: "/wallet" },
  {
    label: "Subscriptions",
    children: [
      { label: "Vendor Setup", to: "/subscriptions/vendor-creation" },
      { label: "Manage Plans", to: "/subscriptions/manage" },
      { label: "Plan History", to: "/subscriptions/history" },
    ],
  },
  { label: "Financial Snapshots", to: "/snapshots" },
  { label: "Monthly Limit", to: "/spending-guard" },
  { label: "Payment History", to: "/history" },
];
</script>

<template>
  <nav class="menu" aria-label="Main">
    <AppMenuItem v-for="item in items" :key="item.to || item.label" :item="item" />
  </nav>
</template>

<style scoped>
.menu {
  display: grid;
  gap: 0.25rem;
  align-content: start;
  justify-items: stretch;
  grid-auto-rows: min-content;
}
</style>
