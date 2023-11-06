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
import {FaPause, FaRegSmile, FaTimes} from "react-icons/fa";
import {FaStop} from "react-icons/fa";
import {Build, Builder, DataCollection, Master, Worker} from "buildbot-data-js";
import {Link} from "react-router-dom";
import {BadgeRound, BuildLinkWithSummaryTooltip} from "buildbot-ui";
import {observer} from "mobx-react";

export const getWorkerStatusIcon = (worker: Worker, onClick: () => void) => {
  if (worker.paused) {
    return (
      <FaPause title="paused" onClick={onClick}>&nbsp;</FaPause>
    );
  }
  if (worker.graceful) {
    return (
      <FaStop title="graceful shutdown" onClick={onClick}/>
    );
  }
  if (worker.connected_to.length > 0) {
    return (
      <FaRegSmile onClick={onClick}/>
    );
  }
  return (<></>);
}

const anyWorkerPaused = (workers: Worker[]) => {
  for (let w of workers) {
    if (w.paused) {
      return true;
    }
  }
  return false;
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

export const WorkersTable = observer(({workers, buildersQuery, mastersQuery,
                                       buildsForWorker, onWorkerIconClick}: WorkersTableProps) => {
  const workerInfoNamesToDisplay = getWorkerInfoNamesToDisplay(workers);

  const renderConnectedMasters = (worker: Worker) => {
    if (worker.connected_to.length === 0) {
      return (
        <div key="disconnected">
          <FaTimes title="disconnected" className="text-danger"/>
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

  const renderPauseReason = (worker: Worker, displayPauseReason: boolean) => {
    if (!displayPauseReason) {
      return <></>;
    }
    return (
      <td key="worker-paused">
        {worker.paused ? worker.pause_reason : ""}
      </td>
    );
  }

  const renderWorkerRow = (worker: Worker, displayPauseReason: boolean) => {
    return (
      <tr key={worker.name}>
        <td key="state">{getWorkerStatusIcon(worker, () => onWorkerIconClick(worker))}</td>
        {renderPauseReason(worker, displayPauseReason)}
        <td key="masters">{renderConnectedMasters(worker)}</td>
        <td key="name"><Link to={`/workers/${worker.workerid}`}>{worker.name}</Link></td>
        { buildsForWorker === null ? <></> : <td key="builds">{renderWorkerRecentBuilds(worker)}</td> }
        {renderWorkerInfos(worker)}
      </tr>
    );
  }

  const displayPauseReason = anyWorkerPaused(workers);

  return (
    <Table hover striped size="sm">
      <thead>
      <tr>
        <th key="state">State</th>
        { displayPauseReason ? <th key="pause-reason">Pause reason</th> : <></> }
        <th key="masters">Masters</th>
        <th key="name">WorkerName</th>
        { buildsForWorker === null ? <></> : <th key="builds">Recent Builds</th> }
        { workerInfoNamesToDisplay.map(name => <th key={"info-" + name}>{name}</th>) }
      </tr>
      </thead>
      <tbody>
        {workers.map(worker => renderWorkerRow(worker, displayPauseReason))}
      </tbody>
    </Table>
  );
});
