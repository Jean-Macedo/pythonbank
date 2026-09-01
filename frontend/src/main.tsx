import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from './App'
import './estilos/global.css'
import { aplicarTema, temaGuardado } from './tema'

// antes de renderizar, para não haver piscada de tema errado
aplicarTema(temaGuardado())

createRoot(document.getElementById('raiz')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
