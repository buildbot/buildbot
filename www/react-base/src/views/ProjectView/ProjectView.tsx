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
import {useTagFilterManager, useTopbarItems} from "buildbot-ui";
import {useParams} from "react-router-dom";
import {buildbotSetupPlugin} from "buildbot-plugin-support";
import {Project, useDataAccessor, useDataApiQuery} from "buildbot-data-js";
import {ProjectBuildersWidget} from "../../components/ProjectWidgets/ProjectBuildersWidget";
import {ProjectChangesWidget} from "../../components/ProjectWidgets/ProjectChangesWidget";
import {
  ProjectPendingBuildRequestsWidget
} from "../../components/ProjectWidgets/ProjectPendingBuildRequestsWidget";

export const ProjectView = observer(() => {
  const projectid = Number.parseInt(useParams<"projectid">().projectid ?? "");
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

  return (
    <div className="bb-project-view-container">
      <ProjectBuildersWidget projectid={projectid} filterManager={filterManager}/>
      <ProjectPendingBuildRequestsWidget projectid={projectid}/>
      <ProjectChangesWidget projectid={projectid}/>
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
