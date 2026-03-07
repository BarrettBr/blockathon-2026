import { createApp } from "vue";
import { createPinia } from "pinia";
import PrimeVue from "primevue/config";
import Button from 'primevue/button';
import Card from 'primevue/card';

import App from "./App.vue";
import router from "./router";
import "./assets/main.scss";

const app = createApp(App);

app.use(createPinia());
app.use(router);
app.use(PrimeVue);

app.component('Button', Button);
app.component('Card', Card);

app.mount("#app");
