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
import {Table} from "react-bootstrap";
import {useDataAccessor, useDataApiQuery} from "../../data/ReactUtils";
import {globalMenuSettings} from "../../plugins/GlobalMenuSettings";
import {globalRoutes} from "../../plugins/GlobalRoutes";
import {Worker} from "../../data/classes/Worker";
import {Master} from "../../data/classes/Master";
import {computed} from "mobx";
import {Build} from "../../data/classes/Build";
import {Link} from "react-router-dom";
import {durationFromNowFormat, useCurrentTime} from "../../util/Moment";
import BuildLinkWithSummaryTooltip
  from "../../components/BuildLinkWithSummaryTooltip/BuildLinkWithSummaryTooltip";
import {Builder} from "../../data/classes/Builder";
import BadgeRound from "../../components/BadgeRound/BadgeRound";


const MastersView = observer(() => {
  const now = useCurrentTime();
  const accessor = useDataAccessor([]);

  const mastersQuery = useDataApiQuery(() => Master.getAll(accessor));
  const workersQuery = useDataApiQuery(() => Worker.getAll(accessor));
  const buildsQuery = useDataApiQuery(
    () => Build.getAll(accessor, {query: {limit: 100, order: '-started_at'}}));
  const buildersQuery = useDataApiQuery(() => Builder.getAll(accessor));

  const masterIdToConnectedWorkers = computed(() => {
    const res: {[masterid: string]: Worker[]} = {};
    for (const worker of workersQuery.array) {
      for (const connectedTo of worker.connected_to) {
        const masterid = connectedTo.masterid.toString();
        if (masterid in res) {
          res[masterid].push(worker);
        } else {
          res[masterid] = [worker];
        }
      }
    }
    for (const workers of Object.values(res)) {
      workers.sort((a, b) => a.name.localeCompare(b.name));
    }
    return res;
  }).get();

  const renderWorkersForMaster = (master: Master) => {
    if (!(master.id in masterIdToConnectedWorkers)) {
      return <></>;
    }
    return masterIdToConnectedWorkers[master.id].map(worker => (
      <span>
        <Link to={`/workers/${worker.id}`}>
          <BadgeRound className="results_SUCCESS">
            {worker.name}
          </BadgeRound>
        </Link>
      </span>
    ));
  }

  const renderBuild = (build: Build) => {
    const builder = buildersQuery.getByIdOrNull(build.builderid.toString());
    if (builder === null) {
      return <></>;
    }
    return <BuildLinkWithSummaryTooltip build={build} builder={builder}/>
  };

  const renderMaster = (master: Master) => {
    return (
      <tr key={master.id}>
        <td>
          <i className={"fa " + (master.active ? "fa-check text-success" : "fa-times text-danger")}/>
        </td>
        <td>{master.name}</td>
        <td>
          {buildsQuery.resolved && buildersQuery.resolved
            ? buildsQuery.array
              .filter(build => build.masterid === master.masterid)
              .slice(0, 20)
              .map(build => renderBuild(build))
            : <span>Loading...</span>
          }
        </td>
        <td>
          {workersQuery.resolved
            ? renderWorkersForMaster(master)
            : <span>Loading...</span>
          }
        </td>
        <td>
          { master.last_active !== null
            ? durationFromNowFormat(master.last_active, now)
            : "Unknown"
          }</td>
      </tr>
    )
  }

  return (
    <div className="container">
      <Table hover striped size="sm">
        <tbody>
        <tr>
          <th>Active</th>
          <th>Name</th>
          <th>Recent Builds</th>
          <th>Workers</th>
          <th>Last Active</th>
        </tr>
        {mastersQuery.array.map(master => renderMaster(master))}
        </tbody>
      </Table>
    </div>
  );
});

globalMenuSettings.addGroup({
  name: 'masters',
  parentName: 'builds',
  caption: 'Build Masters',
  icon: null,
  order: null,
  route: '/masters',
});

globalRoutes.addRoute({
  route: "masters",
  group: "builds",
  element: () => <MastersView/>,
});

export default MastersView;
