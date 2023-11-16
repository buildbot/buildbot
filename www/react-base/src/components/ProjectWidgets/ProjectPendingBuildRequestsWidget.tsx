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
import {Card} from "react-bootstrap";
import {
  Project,
  useDataAccessor,
  useDataApiQuery,
  useDataApiSingleElementQuery, Buildrequest, useDataApiDynamicQuery,
} from "buildbot-data-js";
import {buildbotGetSettings} from "buildbot-plugin-support";
import {LoadingSpan} from "../LoadingSpan/LoadingSpan";
import {PendingBuildRequestsTable} from "../PendingBuildRequestsTable/PendingBuildRequestsTable";

export type ProjectPendingBuildRequestsWidgetProps = {
  projectid: number;
}

export const ProjectPendingBuildRequestsWidget = observer(({projectid}: ProjectPendingBuildRequestsWidgetProps) => {
  const accessor = useDataAccessor([]);

  const projectQuery = useDataApiQuery(() => Project.getAll(accessor, {query: {
      projectid: projectid
    }}));
  const project = projectQuery.getNthOrNull(0);
  const builders = useDataApiSingleElementQuery(project, p => p.getBuilders());
  const builderIds = builders.array.map(builder => builder.builderid);

  const buildRequestFetchLimit = buildbotGetSettings().getIntegerSetting("BuildRequests.buildrequestFetchLimit");
  const buildRequestsQuery = useDataApiDynamicQuery(builderIds,
    () => Buildrequest.getAll(accessor, {query: {
        limit: buildRequestFetchLimit,
        order: ['-priority', '-submitted_at'],
        claimed: false,
        builderid__eq: builderIds,
      }}));

  const renderContent = () => {
    if (!buildRequestsQuery.resolved) {
      return <LoadingSpan/>
    }
    if (buildRequestsQuery.array.length === 0) {
      return <span>None</span>
    }
    return (
      <PendingBuildRequestsTable buildRequestsQuery={buildRequestsQuery}/>
    );
  }

  return (
    <Card>
      <Card.Body>
        <h5>Pending Build Requests</h5>
        {renderContent()}
      </Card.Body>
    </Card>
  );
});
