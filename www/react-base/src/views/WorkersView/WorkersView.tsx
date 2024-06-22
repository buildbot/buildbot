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
import {useState} from "react";
import {buildbotGetSettings, buildbotSetupPlugin} from "buildbot-plugin-support";
import {
  Build,
  Builder,
  DataCollection,
  Master,
  Worker,
  useDataAccessor,
  useDataApiQuery
} from "buildbot-data-js";
import {WorkerActionsModal} from "../../components/WorkerActionsModal/WorkerActionsModal";
import {WorkersTable} from "../../components/WorkersTable/WorkersTable";

const isWorkerFiltered = (worker: Worker, showOldWorkers: boolean) => {
  if (showOldWorkers) {
    return true;
  }
  return worker.configured_on.length !== 0;
}

// Returns an object mapping worker name to its known builds. The returned object has an entry
// for each worker in workersQuery.
const getBuildsForWorkerMap = (workersQuery: DataCollection<Worker>,
                               buildsQuery: DataCollection<Build>,
                               maxBuilds: number) => {
  const map : {[workername: string]: Build[]} = {};
  for (const name of workersQuery.array.map(worker => worker.name)) {
    map[name] = [];
  }

  for (const build of buildsQuery.array) {
    if (!('workername' in build.properties)) {
      // This may happen when WorkersView gets information of a new build via websocket update.
      // FIXME: the internal API should re-request full data about build in such case
      continue;
    }
    const workername = build.properties['workername'][0];
    if (!(workername in map)) {
      // This means that workername is not in validNames either
      continue;
    }
    const buildsArray = map[workername];
    if (buildsArray.length >= maxBuilds) {
      continue;
    }
    // builds array is already sorted by decreasing build id
    buildsArray.push(build);
  }

  return map;
}

export const WorkersView = observer(() => {
  const accessor = useDataAccessor([]);

  const showOldWorkers = buildbotGetSettings().getBooleanSetting("Workers.show_old_workers");

  const workersQuery = useDataApiQuery(() => Worker.getAll(accessor, {query: {order: 'name'}}));
  const buildersQuery = useDataApiQuery(() => Builder.getAll(accessor));
  const mastersQuery = useDataApiQuery(() => Master.getAll(accessor));
  const buildsQuery = useDataApiQuery(() =>
    Build.getAll(accessor, {query: {
        property: ["owners", "workername", "branch"],
        limit: 200,
        order: '-buildid'
      }
    }));

  const [workerForActions, setWorkerForActions] = useState<null|Worker>(null);

  const filteredWorkers = workersQuery.array.filter(worker => {
    return isWorkerFiltered(worker, showOldWorkers);
  }).sort((a, b) => a.name.localeCompare(b.name))
    .sort((a, b) => b.connected_to.length - a.connected_to.length);

  return (
    <div className="container">
      <WorkersTable workers={filteredWorkers} buildersQuery={buildersQuery}
                    mastersQuery={mastersQuery}
                    buildsForWorker={getBuildsForWorkerMap(workersQuery, buildsQuery, 7)}
                    onWorkerIconClick={(worker) => setWorkerForActions(worker)}/>
      { workerForActions !== null
        ? <WorkerActionsModal worker={workerForActions}
                              onClose={() => setWorkerForActions(null)}/>
        : <></>
      }
    </div>
  );
});

buildbotSetupPlugin((reg) => {
  reg.registerMenuGroup({
    name: 'workers',
    parentName: 'builds',
    caption: 'Workers',
    order: null,
    route: '/workers',
  });

  reg.registerRoute({
    route: "workers",
    group: "workers",
    element: () => <WorkersView/>,
  });

  reg.registerSettingGroup({
    name: 'Workers',
    caption: 'Workers page related settings',
    items: [{
      type: 'boolean',
      name: 'show_old_workers',
      caption: 'Show old workers',
      defaultValue: false
    }]
  });
});
