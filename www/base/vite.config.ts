import {defineConfig, PluginOption, ViteDevServer} from "vite";
import react from "@vitejs/plugin-react";
import {nodePolyfills} from 'vite-plugin-node-polyfills';
import {viteStaticCopy} from 'vite-plugin-static-copy';
import checker from 'vite-plugin-checker';
import path from 'path';
import fs from 'fs';
import { visualizer } from "rollup-plugin-visualizer";

const proxy = new URL('https://buildbot.buildbot.net');

const proxyTargetHttp = proxy.href.replace(/\/*$/, ''); // trim trailing slashes
const proxyTargetWs = proxy.protocol === 'https:' ? `wss://${proxy.host}` : `ws://${proxy.host}`;

const outDir = 'buildbot_www/static';

const buildPluginsPathsMap = () => {
  const root = path.resolve(__dirname, '..');
  const aliases: {[src: string]: [string, string]} = {}

  const addPlugin = (pluginName: string, pluginOutputRoot: string) => {
    const knownPaths = [
      ['scripts.js', 'text/javascript'],
      ['styles.css', 'text/css']
    ];

    for (const [filename, mimeType] of knownPaths) {
      const pluginOutputFile = path.join(pluginOutputRoot, filename);
      if (fs.existsSync(pluginOutputFile)) {
        aliases[`/plugins/${pluginName}/${filename}`] = [pluginOutputFile, mimeType];
      }
    }
  }

  addPlugin('grid_view', path.join(root, `grid_view/buildbot_grid_view/static/`))
  addPlugin('console_view', path.join(root, `console_view/buildbot_console_view/static/`))
  addPlugin('waterfall_view', path.join(root, `waterfall_view/buildbot_waterfall_view/static/`))
  addPlugin('wsgi_dashboards', path.join(root, `wsgi_dashboards/buildbot_wsgi_dashboards/static/`))

  return aliases;
}

function serveBuildbotPlugins(): PluginOption {
  return {
    apply: 'serve',
    configureServer(server: ViteDevServer) {
      const pathMap = buildPluginsPathsMap();

      return () => {
        server.middlewares.use(async (req, res, next) => {
          if (req.originalUrl !== undefined && (req.originalUrl in pathMap)) {
            const [filePath, mimeType] = pathMap[req.originalUrl];
            res.setHeader('Content-Type', mimeType);
            res.writeHead(200);
            res.write(fs.readFileSync(filePath));
            res.end();
          }

          next();
        });
      };
    },
    name: 'serve-buildbot-plugins',
  };
}

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
    checker({typescript: true}),
    serveBuildbotPlugins(),
    nodePolyfills({
      include: ['util'],
      globals: { process: true },
    }),
    visualizer(),
  ],
  // this makes all path references into relative paths, thus Buildbot can be hosted at a custom
  // path prefix, like my-domain.com/custom-buildbot-path/
  base: './',
  build: {
    target: ['es2020'],
    outDir: outDir,
    emptyOutDir: true,
  },
  test: {
    environment: "jsdom",
  },
  server: {
    proxy: {
      '/auth': proxyTargetHttp,
      '/config': proxyTargetHttp,
      '/api/v2': {
        target: proxyTargetHttp,
        headers: {
          'Host': proxy.host,
          'Origin': proxyTargetHttp,
        },
        // note that changeOrigin does not work for POST requests
      },
      '/login': proxyTargetHttp,
      '/ws': {
        target: proxyTargetWs,
        ws: true,
        secure: false, // the proxy attempts to verify certificate using localhost hostname
        headers: {
          'Host': proxy.host,
          'Origin': proxyTargetHttp,
        },
      },
      '/avatar': proxyTargetHttp,
      '/img': proxyTargetHttp,
      '/browser-warning.js': proxyTargetHttp,
      '/browser-warning.css': proxyTargetHttp,
    },
  },
  resolve: {
    dedupe: [
      'axios',
      'mobx',
      'mobx-react',
      'moment',
      'react',
      'react-dom',
      'react-router-dom'
    ],
    mainFields: ['browser', 'module', 'main']
  },
});
