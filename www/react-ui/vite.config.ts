import {resolve} from "path";
import {defineConfig} from "vite";
import react from "@vitejs/plugin-react";
import dts from 'vite-plugin-dts'
import {viteStaticCopy} from 'vite-plugin-static-copy';

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
    viteStaticCopy({
      targets: [
        { src: './src/styles/colors.scss',
          dest: '',
          rename: 'colors.scss'
        },
      ],
    }),
  ],
  build: {
    lib: {
      entry: resolve(__dirname, 'src/main.ts'),
      name: "buildbotUi",
      fileName: "buildbot-ui",
    },
    rollupOptions: {
      external: [
        'axios',
        'buildbot-data-js',
        'mobx',
        'moment',
        'react',
        'react-dom',
        'react-router-dom'
      ],
      output: {
        globals: {
          axios: "axios",
          "buildbot-data-js": "BuildbotDataJs",
          mobx: "mobx",
          react: "React",
          moment: "moment",
          "react-dom": "ReactDOM",
          "react-router-dom": "ReactRouterDOM",
        },
      },
    },
    target: ['es2015'],
    outDir: outDir,
    emptyOutDir: true,
  },
  define: {
    'process.env.NODE_ENV': '"production"',
  },
});
