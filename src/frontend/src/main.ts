import { createApp } from "vue";
import { createPinia } from "pinia";
import PrimeVue from "primevue/config";
import Button from 'primevue/button';
import Card from 'primevue/card';
import "./assets/main.scss";
import Aura from '@primevue/themes/aura';

import App from "./App.vue";
import router from "./router";

const app = createApp(App);

app.use(createPinia());
app.use(router);
app.use(PrimeVue, {
    theme: {
        preset: Aura
    }
});

app.component('Button', Button);
app.component('Card', Card);

app.mount("#app");
