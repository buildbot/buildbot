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
import {
  Buildrequest,
  useDataAccessor,
  useDataApiQuery
} from "buildbot-data-js";
import {buildbotGetSettings, buildbotSetupPlugin} from "buildbot-plugin-support";
import {LoadingSpan} from "../../components/LoadingSpan/LoadingSpan";
import {
  PendingBuildRequestsTable
} from "../../components/PendingBuildRequestsTable/PendingBuildRequestsTable";
import {TableHeading} from "../../components/TableHeading/TableHeading";

export const PendingBuildRequestsView = observer(() => {
  const accessor = useDataAccessor([]);

  const buildRequestFetchLimit = buildbotGetSettings().getIntegerSetting("BuildRequests.buildrequestFetchLimit");
  const buildRequestsQuery = useDataApiQuery(
    () => Buildrequest.getAll(accessor, {query: {
      limit: buildRequestFetchLimit,
      order: ['-priority', '-submitted_at'],
      claimed: false
    }}));

  const renderContents = () => {
    if (!buildRequestsQuery.resolved) {
      return <LoadingSpan/>;
    }
    if (buildRequestsQuery.array.length === 0) {
      return <span>None</span>
    }

    return (
      <PendingBuildRequestsTable buildRequestsQuery={buildRequestsQuery}/>
    );
  }

  return (
    <div className="container">
      <TableHeading>Pending Buildrequests:</TableHeading>
      {renderContents()}
    </div>
  );
});

buildbotSetupPlugin((reg) => {
  reg.registerMenuGroup({
    name: 'pendingbuildrequests',
    parentName: 'builds',
    caption: 'Pending Buildrequests',
    order: null,
    route: '/pendingbuildrequests',
  });

  reg.registerRoute({
    route: "pendingbuildrequests",
    group: "builds",
    element: () => <PendingBuildRequestsView/>,
  });

  reg.registerSettingGroup({
    name: 'BuildRequests',
    caption: 'Buildrequests page related settings',
    items: [{
      type: 'integer',
      name: 'buildrequestFetchLimit',
      caption: 'Maximum number of pending buildrequests to fetch',
      defaultValue: 50
    }]
  });
});
