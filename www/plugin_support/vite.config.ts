import {resolve} from "path";
import {defineConfig} from "vite";
import dts from 'vite-plugin-dts'
import checker from 'vite-plugin-checker';

const outDir = 'dist';

export default defineConfig({
  plugins: [
    dts(),
    checker({typescript: true}),
  ],
  build: {
    lib: {
      entry: resolve(__dirname, 'src/index.ts'),
      name: "buildbot-plugin-support",
      fileName: "buildbot-plugin-support",
    },
    target: ['es2020'],
    outDir: outDir,
    emptyOutDir: true,
  },
});
