import {observer} from 'mobx-react';
import {useContext, useEffect} from 'react';
import './App.css';
import './styles/styles.scss';
import 'bootstrap';
import {Routes, Route} from 'react-router-dom';
import {ConfigContext, TopbarContext, useCurrentTimeSetupTimers} from 'buildbot-ui';

import {PageWithSidebar} from './components/PageWithSidebar/PageWithSidebar';
import {StoresContext} from './contexts/Stores';
import {globalMenuSettings} from './plugins/GlobalMenuSettings';
import {globalRoutes} from './plugins/GlobalRoutes';
import {Topbar} from './components/Topbar/Topbar';
import {TopbarActions} from './components/TopbarActions/TopbarActions';
import {LoginBar} from './components/LoginBar/LoginBar';

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
import './views/ProjectView/ProjectView';
import './views/ProjectsView/ProjectsView';
import './views/SettingsView/SettingsView';
import './views/SchedulersView/SchedulersView';
import './views/WorkersView/WorkersView';
import './views/WorkerView/WorkerView';
import {AccessForbiddenView} from './views/AccessForbiddenView/AccessForbiddenView';
import {LoginView} from './views/LoginView/LoginView';
import {UrlNotFoundView} from './views/UrlNotFoundView/UrlNotFoundView';

export const App = observer(() => {
  const stores = useContext(StoresContext);
  const config = useContext(ConfigContext);
  const topbarStore = useContext(TopbarContext);

  useEffect(() => {
    globalMenuSettings.setAppTitle(config.title);
  }, [config.title]);

  useCurrentTimeSetupTimers();

  const routeElements = [...globalRoutes.configs.values()].map((config) => {
    return <Route key={config.route} path={config.route} element={config.element()} />;
  });
  routeElements.push(<Route key="*" path="*" element={<UrlNotFoundView />} />);

  if (!config.user_any_access_allowed) {
    return (
      <div className="bb-app-container">
        <Topbar store={topbarStore} appTitle={globalMenuSettings.appTitle}>
          <TopbarActions store={topbarStore} />
        </Topbar>
        {config.user.anonymous ? <LoginView /> : <AccessForbiddenView />}
      </div>
    );
  }

  return (
    <PageWithSidebar menuSettings={globalMenuSettings} sidebarStore={stores.sidebar}>
      <Topbar store={topbarStore} appTitle={globalMenuSettings.appTitle}>
        <TopbarActions store={topbarStore} />
        <LoginBar />
      </Topbar>
      <Routes>{routeElements}</Routes>
    </PageWithSidebar>
  );
});
