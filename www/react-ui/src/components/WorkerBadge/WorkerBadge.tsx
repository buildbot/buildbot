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

import {Link} from "react-router-dom";
import {Worker} from "buildbot-data-js";
import {BadgeRound} from "../BadgeRound/BadgeRound";

const connected2class = (worker: Worker) => {
  if (worker.connected_to.length > 0) {
    return "worker_CONNECTED";
  } else {
    return "worker_DISCONNECTED";
  }
};

type WorkerBadgeProps = {
  worker: Worker;
  showWorkerName: boolean;
}

export const WorkerBadge = ({worker, showWorkerName}: WorkerBadgeProps) => {
  const shownWorkerName = () => (
    <BadgeRound title={worker.name} className={connected2class(worker)}>
      {worker.name}
    </BadgeRound>
  );

  const hoverWorkerName = () => (
    <BadgeRound title={worker.name} className={connected2class(worker)}>
      <div className="badge-inactive">{worker.workerid}</div>
      <div className="badge-active">{worker.name}</div>
    </BadgeRound>
  );

  return (
    <span>
      <Link to={`/workers/${worker.id}`}>
        {showWorkerName ? shownWorkerName() : hoverWorkerName()}
      </Link>
    </span>
  );
}
