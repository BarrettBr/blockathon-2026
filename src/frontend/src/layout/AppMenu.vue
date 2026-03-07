<script setup lang="ts">
import AppMenuItem from "./AppMenuItem.vue";

const items = [
  { label: "Dashboard", to: "/dashboard" },
  { label: "Wallet", to: "/wallet" },
  { label: "Subscriptions", to: "/subscriptions" },
  { label: "Spending Guard", to: "/spending-guard" },
  { label: "History", to: "/history" },
];
</script>

<template>
  <nav class="menu" aria-label="Main">
    <AppMenuItem v-for="item in items" :key="item.to" :item="item" />
  </nav>
</template>

<style scoped>
.menu {
  display: grid;
  gap: 0.25rem;
}
</style>
