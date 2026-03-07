import { defineStore } from "pinia";

export const useLayoutStore = defineStore("layout", {
  state: () => ({
    sidebarOpen: true,
    mobileMenuOpen: false,
  }),
  actions: {
    toggleSidebar() {
      if (window.innerWidth < 992) {
        this.mobileMenuOpen = !this.mobileMenuOpen;
        return;
      }
      this.sidebarOpen = !this.sidebarOpen;
    },
    closeMobileMenu() {
      this.mobileMenuOpen = false;
    },
  },
});
