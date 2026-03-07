import { createRouter, createWebHistory } from "vue-router";

import AppLayout from "@/layout/AppLayout.vue";
import DashboardView from "@/views/DashboardView.vue";
import WalletView from "@/views/WalletView.vue";
import SubscriptionsView from "@/views/SubscriptionsView.vue";
import SpendingGuardView from "@/views/SpendingGuardView.vue";
import HistoryView from "@/views/HistoryView.vue";

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/",
      component: AppLayout,
      children: [
        { path: "", redirect: "/dashboard" },
        { path: "dashboard", name: "dashboard", component: DashboardView },
        { path: "wallet", name: "wallet", component: WalletView },
        { path: "subscriptions", name: "subscriptions", component: SubscriptionsView },
        { path: "spending-guard", name: "spending-guard", component: SpendingGuardView },
        { path: "history", name: "history", component: HistoryView },
      ],
    },
  ],
});

export default router;
