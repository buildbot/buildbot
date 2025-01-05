import {resolve} from "path";
import {defineConfig} from "vite";
import checker from 'vite-plugin-checker';
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
    checker({typescript: true}),
  ],
  build: {
    lib: {
      entry: resolve(__dirname, 'src/main.ts'),
      formats: ["es"],
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
    target: ['es2020'],
    outDir: outDir,
    emptyOutDir: true,
    minify: false,
  },
  test: {
    environment: "jsdom",
    // required to fake nextTick: https://vitest.dev/guide/migration.html#timer-mocks-3925
    pool: "threads"
  },
});
