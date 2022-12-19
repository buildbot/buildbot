import {observer} from "mobx-react";
import React, {useContext, useEffect} from 'react';
import './App.css';
import './globals';
import './styles/styles.scss';
import 'bootstrap';
import {Routes, Route} from "react-router-dom";

import PageWithSidebar from "./components/PageWithSidebar/PageWithSidebar";
import {ConfigContext} from "./contexts/Config";
import {StoresContext} from "./contexts/Stores";
import {globalMenuSettings} from "./plugins/GlobalMenuSettings";
import {globalRoutes} from "./plugins/GlobalRoutes";
import {useCurrentTimeSetupTimers} from "./util/Moment";
import Topbar from "./components/Topbar/Topbar";
import TopbarActions from "./components/TopbarActions/TopbarActions";
import Loginbar from "./components/Loginbar/Loginbar";

// import the views so that they register themselves in the plugin system
import './views/AboutView/AboutView';
import './views/HomeView/HomeView';
import './views/BuildersView/BuildersView';
import './views/BuilderView/BuilderView';
import './views/BuildRequestView/BuildRequestView';
import './views/BuildView/BuildView';
import './views/PendingBuildRequestsView/PendingBuildRequestsView';
import './views/ChangesView/ChangesView';
import './views/ChangeBuildsView/ChangeBuildsView';
import './views/LogView/LogView';
import './views/MastersView/MastersView';
import './views/SettingsView/SettingsView';
import './views/SchedulersView/SchedulersView';
import './views/WorkersView/WorkersView';
import './views/WorkerView/WorkerView';
import UrlNotFoundView from "./views/UrlNotFoundView/UrlNotFoundView";

const App = observer(() => {
  const stores = useContext(StoresContext);
  const config = useContext(ConfigContext);

  useEffect(() => {
    globalMenuSettings.setAppTitle(config.title);
  }, [config.title]);

  useCurrentTimeSetupTimers();

  const routeElements = [...globalRoutes.configs.values()].map(config => {
    return <Route key={config.route} path={config.route} element={config.element()}/>
  });
  routeElements.push(
    <Route key="*" path="*" element={<UrlNotFoundView/>}/>
  );

  return (
    <PageWithSidebar menuSettings={globalMenuSettings} sidebarStore={stores.sidebar}>
      <Topbar store={stores.topbar} appTitle={globalMenuSettings.appTitle}>
        <TopbarActions store={stores.topbarActions}/>
        <Loginbar/>
      </Topbar>
      <Routes>
        {routeElements}
      </Routes>
    </PageWithSidebar>
  );
});

export default App;
