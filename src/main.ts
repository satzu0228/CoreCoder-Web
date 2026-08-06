import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { create } from 'naive-ui'
import App from './App.vue'

const app = createApp(App)
const naive = create({})

app.use(createPinia())
app.use(naive)
app.mount('#app')
