import {resolve} from 'path';
import {defineConfig} from 'vite';
import checker from 'vite-plugin-checker';
import react from '@vitejs/plugin-react';
import dts from 'vite-plugin-dts';
import {viteStaticCopy} from 'vite-plugin-static-copy';

const outDir = 'dist';

export default defineConfig({
  plugins: [
    react({
      babel: {
        parserOpts: {
          plugins: ['decorators-legacy', 'classProperties'],
        },
      },
    }),
    checker({typescript: true, eslint: {lintCommand: 'eslint', useFlatConfig: true}}),
    dts(),
    viteStaticCopy({
      targets: [{src: './src/styles/colors.scss', dest: '', rename: 'colors.scss'}],
    }),
  ],
  build: {
    lib: {
      entry: resolve(__dirname, 'src/main.ts'),
      formats: ['es'],
      name: 'buildbotUi',
      fileName: 'buildbot-ui',
    },
    rollupOptions: {
      external: [
        'axios',
        'buildbot-data-js',
        'mobx',
        'mobx-react',
        'moment',
        'react',
        'react-dom',
        'react-router-dom',
      ],
      output: {
        globals: {
          axios: 'axios',
          'buildbot-data-js': 'BuildbotDataJs',
          mobx: 'mobx',
          'mobx-react': 'mobxReact',
          react: 'React',
          moment: 'moment',
          'react-dom': 'ReactDOM',
          'react-router-dom': 'ReactRouterDOM',
        },
      },
    },
    target: ['es2020'],
    outDir: outDir,
    emptyOutDir: true,
  },
  test: {
    environment: 'jsdom',
    // required to fake nextTick: https://vitest.dev/guide/migration.html#timer-mocks-3925
    pool: 'threads',
  },
  define: {
    'process.env.NODE_ENV': '"production"',
  },
});
