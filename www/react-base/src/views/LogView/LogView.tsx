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

import './LogView.scss';
import {observer} from "mobx-react";
import {useNavigate, useParams} from "react-router-dom";
import {buildbotSetupPlugin} from "buildbot-plugin-support";
import {
  Builder,
  Build,
  useDataAccessor,
  useDataApiQuery,
  DataCollection,
  Project
} from "buildbot-data-js";
import {useTopbarItems} from "buildbot-ui";
import {LogViewer} from "../../components/LogViewer/LogViewer";
import {buildTopbarItemsForBuilder} from "../../util/TopbarUtils";

const LogView = observer(() => {
  const builderid = Number.parseInt(useParams<"builderid">().builderid ?? "");
  const buildnumber = Number.parseInt(useParams<"buildnumber">().buildnumber ?? "");
  const stepnumber = Number.parseInt(useParams<"stepnumber">().stepnumber ?? "");
  const logSlug = useParams<"logslug">().logslug ?? "";
  const navigate = useNavigate();

  const accessor = useDataAccessor([builderid, buildnumber, stepnumber]);

  const buildersQuery = useDataApiQuery(() => Builder.getAll(accessor, {id: builderid.toString()}));
  const builder = buildersQuery.getNthOrNull(0);

  const buildsQuery = useDataApiQuery(() => Build.getAll(accessor, {query: {
    builderid: builderid,
    number__eq: buildnumber}
  }));
  const stepsQuery = useDataApiQuery(() => buildsQuery.getRelated(b => b.getSteps({query: {
    number__eq: stepnumber}
  })));
  const logsQuery = useDataApiQuery(() => stepsQuery.getRelated(s => s.getLogs({query: {
    slug__eq: logSlug
  }})));
  const projectsQuery = useDataApiQuery(() => buildersQuery.getRelated(builder => {
    return builder.projectid === null
      ? new DataCollection<Project>()
      : Project.getAll(accessor, {id: builder.projectid.toString()})
  }));

  const build = buildsQuery.getNthOrNull(0);
  const step = stepsQuery.getNthOrNull(0);
  const log = logsQuery.getNthOrNull(0);
  const project = projectsQuery.getNthOrNull(0);

  if (buildsQuery.resolved && build === null) {
    navigate(`/builders/${builderid}/builds/${buildnumber}`);
  }

  useTopbarItems(buildTopbarItemsForBuilder(builder, project, [
    {caption: buildnumber.toString(), route: `/builders/${builderid}/builds/${buildnumber}`},
    {caption: step === null ? "" : step.name, route: null},
    {caption: log === null ? "" : log.name,
     route: `/builders/${builderid}/builds/${buildnumber}/steps/${stepnumber}/logs/${logSlug}`},
  ]));

  return (
    <div className="container bb-logview">
      {
        log === null ? <></> : <LogViewer log={log}/>
      }
    </div>
  );
});

buildbotSetupPlugin((reg) => {
  reg.registerRoute({
    route: "builders/:builderid/builds/:buildnumber/steps/:stepnumber/logs/:logslug",
    group: null,
    element: () => <LogView/>,
  });
});
