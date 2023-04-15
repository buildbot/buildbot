import {defineConfig, PluginOption, ViteDevServer} from "vite";
import react from "@vitejs/plugin-react";
import {viteStaticCopy} from 'vite-plugin-static-copy';
import checker from 'vite-plugin-checker';
import path from 'path';
import fs from 'fs';

const proxyHost = 'buildbot.buildbot.net';
const proxyTargetHttp = `http://${proxyHost}`;
const proxyTargetWs = `ws://${proxyHost}`;
const outDir = 'buildbot_www_react/static';

const buildPluginsPathsMap = () => {
  const root = path.resolve(__dirname, '..');
  const aliases: {[src: string]: [string, string]} = {}

  const addPlugin = (pluginName: string, pluginOutputRoot: string) => {
    const knownPaths = [
      ['js', 'scripts.js', 'text/javascript'],
      ['css', 'styles.css', 'text/css']
    ];

    for (const [type, filename, mimeType] of knownPaths) {
      const pluginOutputFile = path.join(pluginOutputRoot, filename);
      if (fs.existsSync(pluginOutputFile)) {
        aliases[`/plugins/${pluginName}.${type}`] = [pluginOutputFile, mimeType];
      }
    }
  }

  addPlugin('grid_view', path.join(root, `react-grid_view/buildbot_react_grid_view/static/`))
  addPlugin('console_view', path.join(root, `react-console_view/buildbot_react_console_view/static/`))

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
      '/img': proxyTargetHttp,
      '/browser-warning.js': proxyTargetHttp,
      '/browser-warning.css': proxyTargetHttp,
    },
  },
});
