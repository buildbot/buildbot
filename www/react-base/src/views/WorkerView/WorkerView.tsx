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
import {globalRoutes} from "../../plugins/GlobalRoutes";
import {useDataAccessor, useDataApiQuery} from "buildbot-data-js/src/data/ReactUtils";
import {Builder} from "buildbot-data-js/src/data/classes/Builder";
import {Master} from "buildbot-data-js/src/data/classes/Master";
import {Worker} from "buildbot-data-js/src/data/classes/Worker";
import {Build} from "buildbot-data-js/src/data/classes/Build";
import {useParams} from "react-router-dom";
import WorkersTable from "../../components/WorkersTable/WorkersTable";
import BuildsTable from "../../components/BuildsTable/BuildsTable";

const WorkerView = observer(() => {
  const workerid = Number.parseInt(useParams<"workerid">().workerid ?? "");
  const accessor = useDataAccessor([workerid]);

  const workersQuery = useDataApiQuery(() => Worker.getAll(accessor, {id: workerid.toString()}));
  const buildersQuery = useDataApiQuery(() => Builder.getAll(accessor));
  const mastersQuery = useDataApiQuery(() => Master.getAll(accessor));
  const buildsQuery = useDataApiQuery(() =>
    Build.getAll(accessor, {query: {
        property: ["owners", "workername"],
        workerid__eq: workerid,
        limit: 100,
        order: "-buildid",
      }
    }));

  return (
    <div className="container">
      <WorkersTable workers={workersQuery.array} buildersQuery={buildersQuery}
                    mastersQuery={mastersQuery}
                    buildsForWorker={null} onWorkerIconClick={(w) => {}}/>
      <BuildsTable builds={buildsQuery} builders={buildersQuery}/>
    </div>
  );
});

globalRoutes.addRoute({
  route: "workers/:workerid",
  group: "workers",
  element: () => <WorkerView/>,
});


export default WorkerView;
