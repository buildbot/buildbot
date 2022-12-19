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

import {Table} from "react-bootstrap";
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

export const getWorkerStatusIcon = (worker: Worker, onClick: () => void) => {
  if (worker.paused) {
    return (
      <i title="paused" className="fa fa-pause" onClick={onClick}>&nbsp;</i>
    );
  }
  if (worker.graceful) {
    return (
      <i title="graceful shutdown" className="fa fa-stop" onClick={onClick}></i>
    );
  }
  if (worker.connected_to.length > 0) {
    return (
      <i className="fa fa-smile-o" onClick={onClick}></i>
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
  onWorkerIconClick: (worker: Worker) => void;
};

const WorkersTable = observer(({workers, buildersQuery, mastersQuery,
                                buildsForWorker, onWorkerIconClick}: WorkersTableProps) => {
  const workerInfoNamesToDisplay = getWorkerInfoNamesToDisplay(workers);

  const renderConnectedMasters = (worker: Worker) => {
    if (worker.connected_to.length === 0) {
      return (
        <div key="disconnected">
          <i title="disconnected" className="fa fa-times text-danger"></i>
        </div>
      );
    }

    return worker.connected_to.map(connectedMaster => {
      const masterid = connectedMaster.masterid;
      const master = mastersQuery.getByIdOrNull(masterid.toString());
      return (
        <div key={`master-${masterid}`}>
          <Link to={`/masters/${masterid}`}>
            <BadgeRound title={master !== null ? master.name : ""} className="results_SUCCESS">
              {masterid.toString()}
            </BadgeRound>
          </Link>
        </div>
      );
    });
  }

  const renderWorkerRecentBuilds = (worker: Worker) => {
    if (buildsForWorker === null) {
      return <></>;
    }
    return buildsForWorker[worker.name].map(build => {
      const builder = buildersQuery.getByIdOrNull(build.builderid.toString());

      return (
        <BuildLinkWithSummaryTooltip key={build.id} build={build} builder={builder}/>
      );
    })
  }

  const renderWorkerInfos = (worker: Worker) => {
    return workerInfoNamesToDisplay.map(name => {
      let info = worker.workerinfo[name];
      if (info === undefined) {
        info = '';
      }

      return (
        <td key={"info-" + name}>
          {name === 'access_uri'
            ? <a href={info}>{info}</a>
            : <>{info}</>
          }
        </td>
      );
    });
  }

  const renderWorkerRow = (worker: Worker) => {
    return (
      <tr key={worker.name}>
        <td key="state">{getWorkerStatusIcon(worker, () => onWorkerIconClick(worker))}</td>
        <td key="masters">{renderConnectedMasters(worker)}</td>
        <td key="name"><Link to={`/workers/${worker.workerid}`}>{worker.name}</Link></td>
        <td key="builds">{renderWorkerRecentBuilds(worker)}</td>
        {renderWorkerInfos(worker)}
      </tr>
    );
  }

  return (
    <Table hover striped size="sm">
      <thead>
      <tr>
        <th key="state">State</th>
        <th key="masters">Masters</th>
        <th key="name">WorkerName</th>
        { buildsForWorker === null ? <></> : <th key="builds">Recent Builds</th> }
        { workerInfoNamesToDisplay.map(name => <th key={"info-" + name}>{name}</th>) }
      </tr>
      </thead>
      <tbody>
        {workers.map(worker => renderWorkerRow(worker))}
      </tbody>
    </Table>
  );
});

export default WorkersTable;
