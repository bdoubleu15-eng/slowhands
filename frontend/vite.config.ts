import { defineConfig } from 'vite'
import electron from 'vite-plugin-electron'
import renderer from 'vite-plugin-electron-renderer'
import { visualizer } from 'rollup-plugin-visualizer'

export default defineConfig({
  plugins: [
    electron([
      {
        // Main-Process entry file of the Electron App.
        entry: 'electron/main.ts',
        vite: {
          build: {
            rollupOptions: {
              external: ['electron']
            }
          }
        },
      },
      {
        entry: 'electron/preload.ts',
        onstart(options) {
          options.reload()
        },
      },
    ]),
    renderer(),
    visualizer({
      open: false,
      filename: 'dist/stats.html',
      gzipSize: true,
      brotliSize: true,
    }),
  ],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('monaco-editor')) {
            if (id.includes('language/typescript') || id.includes('language/javascript')) {
              return 'monaco-lang-ts';
            }
            if (id.includes('language/json')) {
              return 'monaco-lang-json';
            }
            if (id.includes('language/html')) {
              return 'monaco-lang-html';
            }
            if (id.includes('language/css')) {
              return 'monaco-lang-css';
            }
            return 'monaco-core';
          }
        }
      }
    }
  }
})
