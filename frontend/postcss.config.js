/**
 * postcss.config.js — Pipeline de PostCSS para SmartSack.
 * Tailwind procesa las directivas @tailwind y autoprefixer añade los
 * prefijos de proveedor necesarios para navegadores objetivo.
 */
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
