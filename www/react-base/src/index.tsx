import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import "./plugins/GlobalSetup";
import "buildbot-plugin-support";
import App from './App';
import {DataClientContext} from "buildbot-data-js/src/data/ReactUtils";
import DataClient from "buildbot-data-js/src/data/DataClient";
import RestClient, {getRestUrl} from "buildbot-data-js/src/data/RestClient";
import {getWebSocketUrl, WebSocketClient} from "buildbot-data-js/src/data/WebSocketClient";
import {TimeContext} from "buildbot-data-js/src/contexts/Time";
import TimeStore from "buildbot-data-js/src/stores/TimeStore";
import {Config, ConfigContext} from "./contexts/Config";
import {HashRouter} from "react-router-dom";
import SidebarStore from "./stores/SidebarStore";
import { StoresContext } from './contexts/Stores';
import TopbarStore from "./stores/TopbarStore";
import TopbarActionsStore from "./stores/TopbarActionsStore";
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
  const topbarActionsStore = new TopbarActionsStore();
  globalSettings.applyBuildbotConfig(buildbotFrontendConfig);
  globalSettings.load();

  root.render(
    <DataClientContext.Provider value={dataClient}>
      <ConfigContext.Provider value={buildbotFrontendConfig}>
        <TimeContext.Provider value={timeStore}>
          <StoresContext.Provider value={{
            sidebar: sidebarStore,
            topbar: topbarStore,
            topbarActions: topbarActionsStore,
          }}>
            <HashRouter>
              <App/>
            </HashRouter>
          </StoresContext.Provider>
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
