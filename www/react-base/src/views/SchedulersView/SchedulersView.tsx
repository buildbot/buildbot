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
import {buildbotSetupPlugin} from "buildbot-plugin-support";
import {Scheduler, useDataAccessor, useDataApiQuery} from "buildbot-data-js";

export const SchedulersView = observer(() => {
  const accessor = useDataAccessor([]);

  const schedulersQuery = useDataApiQuery(
    () => Scheduler.getAll(accessor, {query: {order: "name"}}));

  const toggleSchedulerEnabled = (scheduler: Scheduler) => {
    const newValue = !scheduler.enabled;
    scheduler.control("enable", {enabled: newValue});
  }

  const renderScheduler = (scheduler: Scheduler) => {
    return (
      <tr key={scheduler.name}>
        <td>
          <input type="checkbox" checked={scheduler.enabled}
                 onClick={() => toggleSchedulerEnabled(scheduler)}/>
        </td>
        <td>{scheduler.name}</td>
        <td>{scheduler.master !== null ? scheduler.master.name : "(none)"}</td>
      </tr>
    )
  }

  return (
    <div className="container">
      <Table hover striped size="sm">
        <tbody>
          <tr>
            <td>Enabled</td>
            <td>Scheduler Name</td>
            <td>Master</td>
          </tr>
          {schedulersQuery.array.map(scheduler => renderScheduler(scheduler))}
        </tbody>
      </Table>
    </div>
  );
});

buildbotSetupPlugin((reg) => {
  reg.registerMenuGroup({
    name: 'schedulers',
    parentName: 'builds',
    caption: 'Schedulers',
    order: null,
    route: '/schedulers',
  });

  reg.registerRoute({
    route: "schedulers",
    group: "schedulers",
    element: () => <SchedulersView/>,
  });
});
