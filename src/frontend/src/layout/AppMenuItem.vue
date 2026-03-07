<script setup lang="ts">
import { computed, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";

interface MenuItem {
  label: string;
  to?: string;
  children?: Array<{ label: string; to: string }>;
}

const props = defineProps<{ item: MenuItem }>();
const route = useRoute();
const expanded = ref(false);

const active = computed(() => !!props.item.to && route.path === props.item.to);
const hasChildren = computed(() => !!props.item.children?.length);
const childActive = computed(() =>
  (props.item.children || []).some((child) => route.path === child.to),
);
const isExpanded = computed(() => expanded.value || childActive.value);

function toggle() {
  expanded.value = !expanded.value;
}
</script>

<template>
  <div class="menu-group">
    <RouterLink
      v-if="item.to"
      :to="item.to"
      class="menu-item"
      :class="{ active }"
    >
      <span>{{ item.label }}</span>
    </RouterLink>

    <button
      v-else
      class="menu-item menu-toggle"
      :class="{ active: childActive }"
      type="button"
      @click="toggle"
    >
      <span>{{ item.label }}</span>
      <span class="caret" :class="{ open: isExpanded }">▾</span>
    </button>

    <div v-if="hasChildren && isExpanded" class="submenu">
      <RouterLink
        v-for="child in item.children"
        :key="child.to"
        :to="child.to"
        class="submenu-item"
        :class="{ active: route.path === child.to }"
      >
        {{ child.label }}
      </RouterLink>
    </div>
  </div>
</template>

<style scoped>
.menu-group {
  display: grid;
  gap: 0.2rem;
}

.menu-item {
  width: 100%;
  text-align: left;
  text-decoration: none;
  color: #355278;
  font-weight: 600;
  padding: 0.7rem 0.85rem;
  border-radius: 10px;
  transition: all 0.2s ease;
  border: none;
  background: transparent;
  font-size: 0.98rem;
}

.menu-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
}

.menu-item:hover {
  background: #ebf3ff;
}

.menu-item.active {
  background: #dfeeff;
  color: #1c4581;
}

.submenu {
  display: grid;
  gap: 0.15rem;
  padding-left: 0.7rem;
}

.submenu-item {
  text-decoration: none;
  color: #50709b;
  font-weight: 600;
  padding: 0.48rem 0.72rem;
  border-radius: 8px;
  font-size: 0.9rem;
}

.submenu-item:hover {
  background: #edf4ff;
}

.submenu-item.active {
  background: #dfeeff;
  color: #1c4581;
}

.caret {
  font-size: 0.8rem;
  transition: transform 0.2s ease;
}

.caret.open {
  transform: rotate(180deg);
}
</style>
