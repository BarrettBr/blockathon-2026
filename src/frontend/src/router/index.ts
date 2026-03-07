import { createRouter, createWebHistory } from "vue-router";

import AppLayout from "@/layout/AppLayout.vue";
import DashboardView from "@/views/DashboardView.vue";
import WalletView from "@/views/WalletView.vue";
import SubscriptionVendorCreationView from "@/views/SubscriptionVendorCreationView.vue";
import SubscriptionManageView from "@/views/SubscriptionManageView.vue";
import SubscriptionHistoryView from "@/views/SubscriptionHistoryView.vue";
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
        { path: "subscriptions", redirect: "/subscriptions/manage" },
        {
          path: "subscriptions/vendor-creation",
          name: "subscription-vendor-creation",
          component: SubscriptionVendorCreationView,
        },
        {
          path: "subscriptions/manage",
          name: "subscription-manage",
          component: SubscriptionManageView,
        },
        {
          path: "subscriptions/history",
          name: "subscription-history",
          component: SubscriptionHistoryView,
        },
        { path: "spending-guard", name: "spending-guard", component: SpendingGuardView },
        { path: "history", name: "history", component: HistoryView },
      ],
    },
  ],
});

export default router;
