<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useSnapshotStore } from "@/stores/snapshot";

const snapshot = useSnapshotStore();

const createForm = reactive({
  title: "",
  days: 30,
  start_date: "",
  end_date: "",
});
const question = ref("");
const message = ref("");
const creatingSnapshot = ref(false);

async function refreshList() {
  await snapshot.loadList();
}

async function createSnapshot() {
  try {
    creatingSnapshot.value = true;
    message.value = "Creating snapshot...";
    const created = await snapshot.create({
      title: createForm.title || undefined,
      days: createForm.days || undefined,
      start_date: createForm.start_date || undefined,
      end_date: createForm.end_date || undefined,
    });
    message.value = `Snapshot #${created.id} created.`;
    await refreshList();
  } catch (error: any) {
    message.value = error?.response?.data?.detail || "Failed to create snapshot";
  } finally {
    creatingSnapshot.value = false;
  }
}

async function openSnapshot(id: number) {
  try {
    await snapshot.open(id);
    message.value = "Snapshot opened.";
  } catch (error: any) {
    message.value = error?.response?.data?.detail || "Failed to open snapshot";
  }
}

async function askQuestion() {
  if (!snapshot.selected?.id || !question.value.trim()) return;
  try {
    await snapshot.ask(snapshot.selected.id, question.value.trim());
    message.value = "Question answered.";
  } catch (error: any) {
    message.value = error?.response?.data?.detail || "Failed to ask question";
  }
}

onMounted(refreshList);
</script>

<template>
  <section class="stack">
    <article class="panel">
      <h3>Create Financial Snapshot</h3>
      <p>Creates an immutable snapshot artifact from current payments/subscriptions and stores it on Pinata.</p>

      <label>Title (optional)</label>
      <input v-model="createForm.title" placeholder="April snapshot before moving" />

      <label>Quick Range: Last N Days</label>
      <input v-model.number="createForm.days" type="number" min="1" max="3650" />

      <p class="or">OR define explicit range</p>

      <div class="date-grid">
        <div>
          <label>Start Date (YYYY-MM-DD)</label>
          <input v-model="createForm.start_date" placeholder="2026-03-01" />
        </div>
        <div>
          <label>End Date (YYYY-MM-DD)</label>
          <input v-model="createForm.end_date" placeholder="2026-03-31" />
        </div>
      </div>

      <div class="row-actions">
        <button class="compact" :disabled="creatingSnapshot" @click="createSnapshot">
          {{ creatingSnapshot ? "Creating..." : "Create Snapshot" }}
        </button>
      </div>
    </article>

    <article class="panel">
      <div class="panel-header">
        <h3>Snapshot List</h3>
        <button class="compact secondary" @click="refreshList">Refresh</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Title</th>
              <th>Created</th>
              <th>Range</th>
              <th>Total Spend (XRP)</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in snapshot.list" :key="row.id">
              <td>#{{ row.id }}</td>
              <td>{{ row.title }}</td>
              <td>{{ row.created_at }}</td>
              <td>{{ row.period_start }} -> {{ row.period_end }}</td>
              <td>{{ row.summary_total_spend_xrp }}</td>
              <td><button class="compact" @click="openSnapshot(row.id)">Open</button></td>
            </tr>
            <tr v-if="snapshot.list.length === 0">
              <td colspan="6">No snapshots yet.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>

    <article v-if="snapshot.selected" class="panel">
      <h3>Snapshot Details</h3>
      <p><strong>{{ snapshot.selected.title }}</strong></p>
      <p>Period: {{ snapshot.selected.period_start }} -> {{ snapshot.selected.period_end }}</p>
      <p>Total: {{ snapshot.selected.summary_total_spend_xrp }} XRP</p>
      <p>Subscriptions: {{ snapshot.selected.summary_total_subscription_xrp }} XRP</p>
      <p>One-time payments: {{ snapshot.selected.summary_total_one_time_xrp }} XRP</p>
      <p>CID: {{ snapshot.selected.pinata_cid }}</p>

      <label>Ask About This Snapshot</label>
      <textarea v-model="question" rows="4" placeholder="How much of my spending is recurring vs one-time?" />
      <button class="compact" @click="askQuestion">Ask Gemini</button>

      <div v-if="snapshot.answer" class="answer">
        <h4>Gemini Answer</h4>
        <p>{{ snapshot.answer }}</p>
      </div>
    </article>

    <p class="message">{{ message || snapshot.error }}</p>
  </section>
</template>

<style scoped>
.stack { display: grid; gap: 1rem; }
.panel {
  background: rgba(255,255,255,0.97);
  border: 1px solid #dceaff;
  border-radius: 14px;
  padding: 1rem;
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.7rem;
}
.panel-header h3 { margin: 0; }
h3 + p { color: #284a73; }
h3 { margin: 0 0 0.7rem; color: #1f467d; }
label { display: block; color: #47678f; font-size: 0.86rem; margin-top: 0.45rem; }
input, textarea {
  width: 100%;
  border: 1px solid #cfe0fb;
  border-radius: 8px;
  padding: 0.5rem 0.65rem;
  margin-top: 0.2rem;
}
.or { margin: 0.5rem 0 0; color: #466995; }
.date-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.75rem; }
.row-actions { display: flex; gap: 0.5rem; margin-top: 0.75rem; }
.compact {
  border: none;
  border-radius: 8px;
  padding: 0.38rem 0.62rem;
  background: linear-gradient(130deg, #2c6fdf, #1f58bf);
  color: #fff;
  font-weight: 700;
  font-size: 0.86rem;
  cursor: pointer;
}
.compact:disabled {
  cursor: not-allowed;
  opacity: 0.72;
}
.compact.secondary { background: #4f79b8; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; min-width: 860px; }
th, td {
  border-bottom: 1px solid #e4efff;
  padding: 0.45rem;
  text-align: left;
  color: #2f4f74;
  font-size: 0.9rem;
}
.answer {
  margin-top: 0.8rem;
  background: #f6faff;
  border: 1px solid #dceaff;
  border-radius: 10px;
  padding: 0.75rem;
}
.answer h4 { margin: 0 0 0.4rem; color: #1f467d; }
.answer p { margin: 0; color: #35577f; white-space: pre-wrap; }
.message { color: #28558e; margin: 0; font-weight: 600; }
@media (max-width: 900px) {
  .date-grid { grid-template-columns: 1fr; }
}
</style>
