import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';
import {DataClientContext} from "./data/ReactUtils";
import DataClient from "./data/DataClient";
import RestClient, {getRestUrl} from "./data/RestClient";
import {getWebSocketUrl, WebSocketClient} from "./data/WebSocketClient";
import {Config, ConfigContext} from "./contexts/Config";
import {HashRouter} from "react-router-dom";
import SidebarStore from "./stores/SidebarStore";
import { StoresContext } from './contexts/Stores';
import TopbarStore from "./stores/TopbarStore";
import {globalSettings} from "./plugins/GlobalSettings";

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

const restClient = new RestClient(getRestUrl(window.location));
const webSocketClient = new WebSocketClient(getWebSocketUrl(window.location),
    url => new WebSocket(url));

const dataClient = new DataClient(restClient, webSocketClient);

// FIXME: the config should come from master
const hardcodedUrl = `${window.location.protocol}://${window.location.hostname}${window.location.port}/`;
const hardcodedConfig: Config = {
  user: { anonymous: true },
  port: "",
  plugins: {},
  auth: { name: "", oauth2: false, fa_icon: "", autologin: false },
  avatar_methods: [],
  versions: [
    ["Python", "3.6.13"],
    ["Buildbot", "3.5.1"],
    ["Twisted", "18.9.0"],
    ["buildbot_travis", "0.6.4"],
    ["buildbot-grid-view", "2.2.1"],
    ["buildbot-codeparameter", "1.6.1"],
  ],
  ui_default_config: {},
  buildbotURL: hardcodedUrl,
  title: "test buildbot",
  titleURL: hardcodedUrl,
  multiMaster: false,
}

const sidebarStore = new SidebarStore();
const topbarStore = new TopbarStore();
globalSettings.applyBuildbotConfig(hardcodedConfig);

root.render(
  <React.StrictMode>
    <DataClientContext.Provider value={dataClient}>
      <ConfigContext.Provider value={hardcodedConfig}>
        <StoresContext.Provider value={{
          sidebar: sidebarStore,
          topbar: topbarStore,
        }}>
          <HashRouter>
            <App />
          </HashRouter>
        </StoresContext.Provider>
      </ConfigContext.Provider>
    </DataClientContext.Provider>
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
