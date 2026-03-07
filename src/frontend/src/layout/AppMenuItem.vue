<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, useRoute } from "vue-router";

const props = defineProps<{ item: { label: string; to: string } }>();
const route = useRoute();

const active = computed(() => route.path === props.item.to);
</script>

<template>
  <RouterLink :to="item.to" class="menu-item" :class="{ active }">
    <span>{{ item.label }}</span>
  </RouterLink>
</template>

<style scoped>
.menu-item {
  text-decoration: none;
  color: #355278;
  font-weight: 600;
  padding: 0.7rem 0.85rem;
  border-radius: 10px;
  transition: all 0.2s ease;
}

.menu-item:hover {
  background: #ebf3ff;
}

.menu-item.active {
  background: #dfeeff;
  color: #1c4581;
}
</style>
