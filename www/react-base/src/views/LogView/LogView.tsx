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
import {globalRoutes} from "../../plugins/GlobalRoutes";
import {useContext} from "react";
import {useTopbarItems} from "../../stores/TopbarStore";
import {StoresContext} from "../../contexts/Stores";
import {useNavigate, useParams} from "react-router-dom";
import {useDataAccessor, useDataApiQuery} from "../../data/ReactUtils";
import {Builder} from "../../data/classes/Builder";
import {Build} from "../../data/classes/Build";
import LogViewer from "../../components/LogViewer/LogViewer";

const LogView = observer(() => {
  const builderid = Number.parseInt(useParams<"builderid">().builderid ?? "");
  const buildnumber = Number.parseInt(useParams<"buildnumber">().buildnumber ?? "");
  const stepnumber = Number.parseInt(useParams<"stepnumber">().stepnumber ?? "");
  const logSlug = useParams<"logslug">().logslug ?? "";
  const navigate = useNavigate();

  const stores = useContext(StoresContext);
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

  const build = buildsQuery.getNthOrNull(0);
  const step = stepsQuery.getNthOrNull(0);
  const log = logsQuery.getNthOrNull(0);

  if (buildsQuery.resolved && build === null) {
    navigate(`/builders/${builderid}/builds/${buildnumber}`);
  }

  useTopbarItems(stores.topbar, [
    {caption: "Builders", route: "/builders"},
    {caption: builder === null ? "..." : builder.name, route: `/builders/${builderid}`},
    {caption: buildnumber.toString(), route: `/builders/${builderid}/builds/${buildnumber}`},
    {caption: step === null ? "" : step.name, route: null},
    {caption: log === null ? "" : log.name,
     route: `/builders/${builderid}/builds/${buildnumber}/steps/${stepnumber}/logs/${logSlug}`},
  ]);

  return (
    <div className="container bb-logview">
      {
        log === null ? <></> : <LogViewer log={log}/>
      }
    </div>
  );
});

globalRoutes.addRoute({
  route: "builders/:builderid/builds/:buildnumber/steps/:stepnumber/logs/:logslug",
  group: null,
  element: () => <LogView/>,
});
