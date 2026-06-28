import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: path.resolve(__dirname, '../../static/flow-editor'),
    emptyOutDir: true,
    rollupOptions: {
      input: path.resolve(__dirname, 'index.html'),
      output: {
        entryFileNames: 'flow-editor.js',
        chunkFileNames: 'chunk-[name].js',
        assetFileNames: 'flow-editor.[ext]',
      },
    },
  },
});
