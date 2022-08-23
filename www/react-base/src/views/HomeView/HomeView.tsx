/*
  This file is part of Buildbot.  Buildbot is free software: you can
  redistribute it and/or modify it under the terms of the GNU General Public
  License as published by the Free Software Foundation, version 2.

  This program is distributed in the hope that it will be useful, but WITHOUT
  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
  FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
  details.

  You should have received a copy of the GNU General Public License along with
  this program; if not, write to the Free Software Foundation, Inc., 51
  Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

  Copyright Buildbot Team Members
*/

import {observer} from "mobx-react";
import {useDataAccessor, useDataApiQuery} from "../../data/ReactUtils";
import {useContext} from "react";
import {Config, ConfigContext} from "../../contexts/Config";
import {globalMenuSettings} from "../../plugins/GlobalMenuSettings";
import {Build} from "../../data/classes/Build";
import {Builder} from "../../data/classes/Builder";
import DataCollection from "../../data/DataCollection";
import BuildSticker from "../../components/BuildSticker/BuildSticker";
import {Link} from "react-router-dom";
import {globalRoutes} from "../../plugins/GlobalRoutes";


function maybeShowUrlWarning(location: Location, config: Config) {
  const urlWithNoFragment = `${location.protocol}://${location.hostname}${location.port}${location.pathname}`;
  if (urlWithNoFragment === config.buildbotURL) {
    return <></>;
  }

  return (
    <div className="alert alert-danger">
      Warning:
      c['buildbotURL'] is misconfigured to
      <pre>{config.buildbotURL}</pre>Should be:
      <pre>{urlWithNoFragment}</pre>
    </div>
  );
}

type BuildsById = {[id: string]: Build}
type BuilderBuilds = {
  builder: Builder;
  builds: BuildsById;
}
type BuildsByBuilder = {[id: string]: BuilderBuilds};

function computeBuildsByBuilder(builders: DataCollection<Builder>,
                                recentBuilds: DataCollection<Build>) {
  const buildsByBuilder: BuildsByBuilder = {};
  for (const build of recentBuilds.array) {
    const builderid = build.builderid.toString();
    if (builderid in builders.byId) {
      const builder = builders.byId[builderid];
      if (!(builderid in buildsByBuilder)) {
        buildsByBuilder[builderid] = {
          builder: builder,
          builds: {}
        };
      }

      buildsByBuilder[builderid].builds[build.id] = build;
    }
  }
  return buildsByBuilder;
}

const HomeView = observer(() => {
  const config = useContext(ConfigContext);
  const accessor = useDataAccessor();

  const buildsRunning = useDataApiQuery(
    () => Build.getAll(accessor, {query: {order: '-started_at', complete: false}}));

  const recentBuilds = useDataApiQuery(
    () => Build.getAll(accessor, {query: {order: '-buildid', complete: true, limit: 20}}));

  const builders = useDataApiQuery(() => Builder.getAll(accessor));

  const buildsByBuilder = computeBuildsByBuilder(builders, recentBuilds);

  return (
    <div className="container">
      {maybeShowUrlWarning(window.location, config)}
      <div className="row">
        <div className="col-sm-12">
          <div className="well">
            <h2>Welcome to buildbot</h2>
            <h4>{buildsRunning.array.length} build{buildsRunning.array.length === 1 ? '' : 's'}
              running currently</h4>
            <ul>
              {
                buildsRunning.array
                  .filter(build => build.complete === false &&
                    build.builderid.toString() in builders.byId)
                  .map(build => {
                    return (
                      <li className="unstyled">
                        <BuildSticker build={build}
                                      builder={builders.byId[build.builderid.toString()]}/>
                      </li>
                    )
                  })
              }
            </ul>
            <h4>{recentBuilds.array.length} recent builds</h4>
            <div className="row">
              {
                Object.values(buildsByBuilder)
                  .sort((a, b) => a.builder.name.localeCompare(b.builder.name))
                  .map(b => {
                    return (
                      <div className="col-md-4">
                        <div className="panel panel-primary">
                          <div className="panel-heading">
                            <h4 className="panel-title">
                              <Link to={`builder/${b.builder.builderid}`}>{b.builder.name}</Link>
                            </h4>
                        </div>
                        <div className="panel-body">
                          {
                            Object.values(b.builds)
                              .sort((a, b) => a.number - b.number)
                              .map(build => {
                                return (
                                  <span key={build.id}>
                                    <BuildSticker build={build} builder={b.builder}/>
                                  </span>
                                );
                              })
                          }
                        </div>
                      </div>
                    </div>
                    )
                })
              }
            </div>
          </div>
        </div>
      </div>
    </div>
  )
});

globalMenuSettings.addGroup({
  name: 'home',
  caption: 'Home',
  icon: 'home',
  order: 1,
  route: '/',
  parentName: null,
});

globalRoutes.addRoute({
  route: "/",
  group: "home",
  element: () => <HomeView/>,
});

export default HomeView;
