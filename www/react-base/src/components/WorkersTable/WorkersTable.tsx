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

import {Builder} from "../../data/classes/Builder";
import {Master} from "../../data/classes/Master";
import {Worker} from "../../data/classes/Worker";
import {Build} from "../../data/classes/Build";
import {Link} from "react-router-dom";
import DataCollection from "../../data/DataCollection";
import BuildLinkWithSummaryTooltip
  from "../../components/BuildLinkWithSummaryTooltip/BuildLinkWithSummaryTooltip";
import {observer} from "mobx-react";
import BadgeRound from "../BadgeRound/BadgeRound";

export const getWorkerStatusIcon = (worker: Worker) => {
  if (worker.paused) {
    return (
      <i title="paused" className="fa fa-pause">&nbsp;</i>
    );
  }
  if (worker.graceful) {
    return (
      <i title="graceful shutdown" className="fa fa-stop"></i>
    );
  }
  if (worker.connected_to.length > 0) {
    return (
      <i className="fa fa-smile-o"></i>
    );
  }
  return (<></>);
}

export const getWorkerInfoNamesToDisplay = (workers: Worker[]) => {
  const namesSet = new Set<string>();
  for (const worker of workers) {
    for (const name in worker.workerinfo) {
      const value = worker.workerinfo[name];
      if (value !== null && value !== undefined) {
        namesSet.add(name);
      }
    }
  }
  return ([...namesSet]).sort();
}

export type WorkersTableProps = {
  workers: Worker[];
  buildersQuery: DataCollection<Builder>;
  mastersQuery: DataCollection<Master>;
  buildsForWorker: {[workername: string]: Build[]} | null;
};

const WorkersTable = observer(({workers, buildersQuery, mastersQuery,
                                buildsForWorker}: WorkersTableProps) => {
  const workerInfoNamesToDisplay = getWorkerInfoNamesToDisplay(workers);

  return (
    <table className="table table-hover table-striped table-condensed">
      <thead>
      <tr>
        <th>State</th>
        <th>Masters</th>
        <th>WorkerName</th>
        { buildsForWorker === null ? <></> : <th key="builds">Recent Builds</th> }
        { workerInfoNamesToDisplay.map(name => <th key={"info-" + name}>{name}</th>) }
      </tr>
      </thead>
      <tbody>
      {
        workers
          .map(worker => {
            // TODO: actions
            return (
              <tr key={worker.name}>
                <td>{getWorkerStatusIcon(worker)}</td>
                <td>
                  <div>
                    {
                      worker.connected_to.length === 0
                        ? <i title="disconnected" className="fa fa-times text-danger"></i>
                        : <></>
                    }
                  </div>
                  {
                    worker.connected_to.map(connectedMaster => {
                      const masterid = connectedMaster.masterid;
                      const master = mastersQuery.getByIdOrNull(masterid.toString());
                      return (
                        <div key={masterid}>
                          <Link to={`/masters/${masterid}`}>
                            <BadgeRound title={master !== null ? master.name : ""} className="results_SUCCESS">
                              {masterid.toString()}
                            </BadgeRound>
                          </Link>
                        </div>
                      );
                    })
                  }
                </td>
                <td><Link to={`/workers/${worker.workerid}`}>{worker.name}</Link></td>
                {
                  buildsForWorker === null
                  ? <></>
                  : <td key="builds">
                      {
                        buildsForWorker[worker.name].map(build => {
                          const builder = buildersQuery.getByIdOrNull(build.builderid.toString());

                          return (
                            <BuildLinkWithSummaryTooltip build={build} builder={builder}/>
                          );
                        })
                      }
                    </td>
                }
                {
                  workerInfoNamesToDisplay.map(name => {
                    let info = worker.workerinfo[name];
                    if (info === undefined) {
                      info = '';
                    }
                    return (
                      <td key={"info-" + name}>{info}</td>
                    );
                  })
                }
              </tr>
            );
          })
      }
      </tbody>
    </table>
  );
});

export default WorkersTable;
