import {resolve} from 'path';
import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import checker from 'vite-plugin-checker';
import {ModuleFormat} from 'rollup';

const outDir = 'buildbot_wsgi_dashboards/static';

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
  ],
  define: {
    'process.env.NODE_ENV': '"production"',
  },
  build: {
    lib: {
      entry: resolve(__dirname, 'src/index.ts'),
      name: 'buildbotWSGIDashboardsPlugin',
      formats: ['umd'],
      fileName: 'scripts',
    },
    rollupOptions: {
      external: [
        'axios',
        'buildbot-data-js',
        'buildbot-ui',
        'mobx',
        'mobx-react',
        'moment',
        'react',
        'react-dom',
        'react-router-dom',
        'buildbot-plugin-support',
      ],
      output: {
        assetFileNames: 'styles.css',
        entryFileNames: 'scripts.js',
        globals: {
          axios: 'axios',
          'buildbot-data-js': 'BuildbotDataJs',
          'buildbot-plugin-support': 'BuildbotPluginSupport',
          'buildbot-ui': 'BuildbotUi',
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
    poolOptions: {
      threads: {
        singleThread: true,
      },
    }
  },
});
