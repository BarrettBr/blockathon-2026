<script setup lang="ts"></script>

<template>
  <section class="page">
    <article class="card">
      <h2>EquiPay</h2>
      <p>This project currently uses wallet-seed connect flow from the Wallet page.</p>
      <RouterLink to="/wallet" class="link">Go To Wallet</RouterLink>
    </article>
  </section>
</template>

<style scoped>
.page { min-height: 100vh; display: grid; place-items: center; }
.card {
  background: white;
  border: 1px solid #dceaff;
  border-radius: 12px;
  padding: 1.5rem;
  text-align: center;
}
.link { color: #245cbf; font-weight: 700; text-decoration: none; }
</style>
