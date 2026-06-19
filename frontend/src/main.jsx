/**
 * main.jsx — Punto de entrada de la aplicación React.
 *
 * Monta el componente <App /> en el div#root del index.html y carga
 * los estilos globales de Tailwind.
 */
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './styles/index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
