import {defineConfig} from "vite";
import react from "@vitejs/plugin-react";
import {viteStaticCopy} from 'vite-plugin-static-copy';

const proxyHost = 'buildbot.buildbot.net';
const proxyTargetHttp = `http://${proxyHost}`;
const proxyTargetWs = `ws://${proxyHost}`;
const outDir = 'buildbot_www_react/static';

export default defineConfig({
  plugins: [
    react({
      babel: {
        parserOpts: {
          plugins: ['decorators-legacy', 'classProperties']
        }
      }
    }),
    viteStaticCopy({
      targets: [
        { src: './node_modules/outdated-browser-rework/dist/outdated-browser-rework.min.js',
          dest: '',
          rename: 'browser-warning.js'
        },
        { src: './node_modules/outdated-browser-rework/dist/style.css',
          dest: '',
          rename: 'browser-warning.css'
        },
      ],
    }),
  ],
  build: {
    target: ['es2015'],
    outDir: outDir,
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/auth': proxyTargetHttp,
      '/config': proxyTargetHttp,
      '/api/v2': proxyTargetHttp,
      '/login': proxyTargetHttp,
      '/ws': {target: proxyTargetWs, ws: true},
      '/avatar': proxyTargetHttp,
      '/browser-warning.js': proxyTargetHttp,
      '/browser-warning.css': proxyTargetHttp,
    },
  },
});
