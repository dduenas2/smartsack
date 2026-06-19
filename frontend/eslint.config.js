/**
 * eslint.config.js — Configuración ESLint (flat config) para SmartSack frontend.
 *
 * Migrado desde el antiguo `.eslintrc.cjs` al formato flat que ESLint 9 usa por
 * defecto (el flag `--ext` y los `.eslintrc.*` quedaron obsoletos). Reglas para
 * React 18 + Hooks + Vite Refresh; las reglas de react-hooks se declaran de forma
 * explícita para no depender de la forma del preset entre versiones del plugin.
 */
import js from '@eslint/js';
import globals from 'globals';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';

export default [
  // Se excluyen el build, dependencias y el proyecto E2E (Playwright corre aparte).
  { ignores: ['dist', 'node_modules', 'e2e'] },

  js.configs.recommended,
  react.configs.flat.recommended,
  react.configs.flat['jsx-runtime'],

  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: { ...globals.browser, ...globals.node },
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    settings: { react: { version: '18.3' } },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      'react/prop-types': 'off',
    },
  },

  // Los tests de Vitest corren con `globals: true`, por lo que describe/it/expect/vi
  // están disponibles sin importarlos.
  {
    files: ['src/**/*.test.{js,jsx}', 'src/test/**/*.{js,jsx}'],
    languageOptions: {
      globals: {
        describe: 'readonly',
        it: 'readonly',
        test: 'readonly',
        expect: 'readonly',
        vi: 'readonly',
        beforeAll: 'readonly',
        afterAll: 'readonly',
        beforeEach: 'readonly',
        afterEach: 'readonly',
      },
    },
  },
];
