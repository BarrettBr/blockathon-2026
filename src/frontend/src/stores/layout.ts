import { defineStore } from "pinia";

export const useLayoutStore = defineStore("layout", {
  state: () => ({
    sidebarOpen: true,
    mobileMenuOpen: false,
    theme: "light" as "light" | "dark",
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
    initTheme() {
      const stored = localStorage.getItem("theme");
      if (stored === "dark" || stored === "light") {
        this.theme = stored;
      } else {
        this.theme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
      }
      this.applyTheme();
    },
    applyTheme() {
      const root = document.documentElement;
      root.classList.remove("theme-light", "theme-dark");
      root.classList.add(this.theme === "dark" ? "theme-dark" : "theme-light");
      root.style.colorScheme = this.theme;
      localStorage.setItem("theme", this.theme);
    },
    toggleTheme() {
      this.theme = this.theme === "dark" ? "light" : "dark";
      this.applyTheme();
    },
  },
});
