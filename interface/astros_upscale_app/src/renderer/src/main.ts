import '@fontsource-variable/inter'
import '@fontsource-variable/jetbrains-mono'
import './assets/main.css'

import { createApp } from 'vue'
import App from './App.vue'
import { applyTheme, getInitialTheme } from './theme'

applyTheme(getInitialTheme())

createApp(App).mount('#app')
