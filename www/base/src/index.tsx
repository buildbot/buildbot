import './globals';
import './globals2';
import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import {initializeGlobalSetup} from "./plugins/GlobalSetup";
import "buildbot-plugin-support";
import {App} from './App';
import {
  DataClient,
  DataClientContext,
  RestClient,
  WebSocketClient,
  getBaseUrl,
  getRestUrl,
  getWebSocketUrl,
} from "buildbot-data-js";
import {
  Config,
  ConfigContext,
  TimeContext,
  TimeStore,
  TopbarContext,
  TopbarStore
} from "buildbot-ui";
import {HashRouter} from "react-router-dom";
import {SidebarStore} from "./stores/SidebarStore";
import { StoresContext } from './contexts/Stores';
import {globalSettings} from "./plugins/GlobalSettings";
import moment from "moment";
import axios from "axios";

const doRender = (buildbotFrontendConfig: Config) => {
  const root = ReactDOM.createRoot(
    document.getElementById('root') as HTMLElement
  );

  const restClient = new RestClient(getRestUrl(window.location));
  const webSocketClient = new WebSocketClient(getWebSocketUrl(window.location),
    url => new WebSocket(url));

  const dataClient = new DataClient(restClient, webSocketClient);


  const timeStore = new TimeStore();
  timeStore.setTime(moment().unix());

  const sidebarStore = new SidebarStore();
  const topbarStore = new TopbarStore();
  initializeGlobalSetup(buildbotFrontendConfig);
  globalSettings.applyBuildbotConfig(buildbotFrontendConfig);
  globalSettings.load();

  for (const pluginKey in buildbotFrontendConfig.plugins) {
    // TODO: in production this could be added to the document by buildbot backend
    const pluginScript = document.createElement('script');
    pluginScript.type = 'text/javascript';
    pluginScript.src = getBaseUrl(window.location, `plugins/${pluginKey}/scripts.js`);
    document.head.appendChild(pluginScript);

    const pluginCss = document.createElement('link');
    pluginCss.rel = 'stylesheet';
    pluginCss.type = 'text/css';
    pluginCss.href = getBaseUrl(window.location, `plugins/${pluginKey}/styles.css`);
    document.head.appendChild(pluginCss);
  }

  root.render(
    <DataClientContext.Provider value={dataClient}>
      <ConfigContext.Provider value={buildbotFrontendConfig}>
        <TimeContext.Provider value={timeStore}>
          <TopbarContext.Provider value={topbarStore}>
            <StoresContext.Provider value={{
              sidebar: sidebarStore,
            }}>
              <HashRouter>
                <App/>
              </HashRouter>
            </StoresContext.Provider>
          </TopbarContext.Provider>
        </TimeContext.Provider>
      </ConfigContext.Provider>
    </DataClientContext.Provider>
  );
};

const windowAny: any = window;
if ("buildbotFrontendConfig" in windowAny) {
  doRender(windowAny.buildbotFrontendConfig);
} else {
  // fallback during development
  axios.get("config").then(response => {
    const config: Config = response.data;
    config.isProxy = true;
    doRender(config);
  });
}
