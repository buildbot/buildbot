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

import './ProjectView.scss';
import {observer} from "mobx-react";
import {
  Config,
  ConfigContext,
  ProjectWidgetsConfig,
  TagFilterManager,
  useTagFilterManager,
  useTopbarItems
} from "buildbot-ui";
import {useContext} from "react";
import {Alert} from "react-bootstrap";
import {useParams} from "react-router-dom";
import {buildbotSetupPlugin} from "buildbot-plugin-support";
import {Project, useDataAccessor, useDataApiQuery} from "buildbot-data-js";
import {ProjectBuildersWidget} from "../../components/ProjectWidgets/ProjectBuildersWidget";
import {ProjectChangesWidget} from "../../components/ProjectWidgets/ProjectChangesWidget";
import {
  ProjectPendingBuildRequestsWidget
} from "../../components/ProjectWidgets/ProjectPendingBuildRequestsWidget";
import {ProjectDescriptionWidget} from "../../components/ProjectWidgets/ProjectDescriptionWidget";

const defaultWidgetsConfig = [
  "description",
  "builders",
  "pending_build_requests",
  "changes"
];

function findProjectWidgetsConfig(config: Config, name: string) {
  if (config.project_widgets === undefined) {
    return defaultWidgetsConfig;
  }

  let fallbackWidgetConfig: ProjectWidgetsConfig|undefined = undefined;
  for (const widgetConfig of config.project_widgets) {
    if (widgetConfig.project_name === name) {
      return widgetConfig.widgets;
    }
    if (widgetConfig.project_name === undefined) {
      fallbackWidgetConfig = widgetConfig;
    }
  }
  if (fallbackWidgetConfig !== undefined) {
    return fallbackWidgetConfig.widgets;
  }
  return defaultWidgetsConfig;
}

type WidgetCallback = (projectId: number, filterManager: TagFilterManager) => JSX.Element;
type KnownWidgetsConfig = {[name: string]: WidgetCallback};

const knownWidgets: KnownWidgetsConfig = {
  "builders": (projectid, filterManager) => (
    <ProjectBuildersWidget key="builders" projectid={projectid} filterManager={filterManager}/>
  ),
  "description": (projectid, filterManager) => (
    <ProjectDescriptionWidget key="description" projectid={projectid}/>
  ),
  "pending_build_requests": (projectid, filterManager) => (
    <ProjectPendingBuildRequestsWidget key="pending_build_requests" projectid={projectid}/>
  ),
  "changes": (projectid, filterManager) => (
    <ProjectChangesWidget key="changes" projectid={projectid}/>
  ),
}

export const ProjectView = observer(() => {
  const projectid = Number.parseInt(useParams<"projectid">().projectid ?? "");
  const config = useContext(ConfigContext);

  const filterManager = useTagFilterManager("tags");

  const accessor = useDataAccessor([projectid]);
  const projectQuery = useDataApiQuery(() => Project.getAll(accessor, {query: {
      projectid: projectid
    }}));
  const project = projectQuery.getNthOrNull(0);

  useTopbarItems([
    {caption: "Projects", route: "/projects"},
    {caption: project !== null ? project.name : "...", route: `/projects/${projectid}`}
  ]);

  const widgetNamesConfig = project === null ? [] : findProjectWidgetsConfig(config, project.name);

  if (project !== null && widgetNamesConfig.length === 0) {
    return (
      <div className="bb-project-view-container">
        <Alert variant="danger">
          <p>No widgets configured for {project.name}</p>
          <p>Check <code>c["www"]["project_widgets"]</code> field in Buildbot configuration</p>
        </Alert>
      </div>
    );
  }

  const renderWidgetNameConfig = (name: string) => {
    const callback = knownWidgets[name];
    if (callback !== null) {
      return callback(projectid, filterManager);
    }
    return (
      <Alert variant="danger">Unknown widget {name}</Alert>
    );
  };

  return (
    <div className="bb-project-view-container">
      {widgetNamesConfig.map(name => renderWidgetNameConfig(name))}
    </div>
  );
});

buildbotSetupPlugin((reg) => {
  reg.registerRoute({
    route: "projects/:projectid",
    group: null,
    element: () => <ProjectView/>,
  });
});
