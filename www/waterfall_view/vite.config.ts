import {resolve} from 'path';
import {defineConfig} from 'vite';
import checker from 'vite-plugin-checker';
import react from '@vitejs/plugin-react';

const outDir = 'buildbot_waterfall_view/static';

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
      name: 'buildbotConsoleViewPlugin',
      formats: ['umd'],
      fileName: 'scripts',
    },
    rollupOptions: {
      external: [
        'axios',
        'buildbot-data-js',
        'buildbot-plugin-support',
        'buildbot-ui',
        'mobx',
        'mobx-react',
        'moment',
        'react',
        'react-dom',
        'react-router-dom',
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
  },
});
