import { createApp } from "vue";

import App from "./App.vue";
import { initAppUpdate } from "./appUpdate";
import "./style.css";

initAppUpdate();

createApp(App).mount("#app");

