import {resolve} from "path";
import {defineConfig} from "vite";
import react from "@vitejs/plugin-react";
import dts from 'vite-plugin-dts'

const outDir = 'dist';

export default defineConfig({
  plugins: [
    react({
      babel: {
        parserOpts: {
          plugins: ['decorators-legacy', 'classProperties']
        }
      }
    }),
    dts(),
  ],
  build: {
    lib: {
      entry: resolve(__dirname, 'src/main.ts'),
      name: "buildbot-data-js",
      fileName: "buildbot-data-js",
    },
    rollupOptions: {
      external: ['axios', 'mobx', 'react', 'moment'],
      output: {
        globals: {
          axios: "axios",
          mobx: "mobx",
          react: "React",
          moment: "moment",
        },
      },
    },
    target: ['es2015'],
    outDir: outDir,
    emptyOutDir: true,
    minify: false,
  },
});
