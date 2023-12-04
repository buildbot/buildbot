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

import './PendingBuildRequestsTable.scss';
import {observer} from "mobx-react";
import {Table} from "react-bootstrap";
import {Link} from "react-router-dom";
import {
  Builder,
  Buildrequest, DataCollection,
  getPropertyValueOrDefault,
  useDataAccessor,
  useDataApiQuery
} from "buildbot-data-js";
import {BadgeRound, dateFormat, durationFromNowFormat, useCurrentTime} from "buildbot-ui";
import {useScrollToAnchor} from "../../util/AnchorLinks";
import {AnchorLink} from "../AnchorLink/AnchorLink";

export type PendingBuildRequestsTableProps = {
  buildRequestsQuery: DataCollection<Buildrequest>;
};

export const PendingBuildRequestsTable = observer(({buildRequestsQuery}: PendingBuildRequestsTableProps) => {
  const now = useCurrentTime();
  const accessor = useDataAccessor([]);

  const propertiesQuery = useDataApiQuery(() =>
    buildRequestsQuery.getRelatedProperties(br => br.getProperties()));
  const buildersQuery = useDataApiQuery(() =>
    buildRequestsQuery.getRelated(br => Builder.getAll(accessor, {id: br.builderid.toString()})));

  useScrollToAnchor(buildRequestsQuery.array.map(buildRequest => buildRequest.id));

  const renderBuildRequests = () => {
    return buildRequestsQuery.array.map(buildRequest => {
      const builder = buildersQuery.getNthOfParentOrNull(buildRequest.id, 0);
      const properties = propertiesQuery.getParentCollectionOrEmpty(buildRequest.id);

      const propertiesElements = Array.from(properties.properties.entries()).map(([name, valueSource]) => {
        return (
          <li key={name}>{name} = {JSON.stringify(valueSource[0])}</li>
        );
      });

      return (
        <tr key={buildRequest.id}
            className="bb-pending-build-request-table-line"
            id={`bb-buildrequest-${buildRequest.id}`}>
          <td>
            <AnchorLink className="bb-pending-build-request-anchor-link"
                        anchor={`bb-buildrequest-${buildRequest.id}`}>
              #
            </AnchorLink>
            <Link to={`/buildrequests/${buildRequest.id}`}>
              <BadgeRound className=''>{buildRequest.id.toString()}</BadgeRound>
            </Link>
          </td>
          <td>
            <Link to={`/builders/${buildRequest.builderid}`}>
              <span>{builder !== null ? builder.name : "Loading ... "}</span>
            </Link>
          </td>
          <td>
            {buildRequest.priority}
          </td>
          <td>
            <span title={dateFormat(buildRequest.submitted_at)}>
              {durationFromNowFormat(buildRequest.submitted_at, now)}
            </span>
          </td>
          <td>
            <span>
              {getPropertyValueOrDefault(buildRequest.properties, "owner", "(none)")}
            </span>
          </td>
          <td>
            <ul>
              {propertiesElements}
            </ul>
          </td>
        </tr>
      );
    });
  }

  return (
    <Table hover striped size="sm">
      <tbody>
      <tr>
        <td width="100px">#</td>
        <td width="150px">Builder</td>
        <td width="100px">Priority</td>
        <td width="150px">Submitted At</td>
        <td width="150px">Owner</td>
        <td width="150px">Properties</td>
      </tr>
      {renderBuildRequests()}
      </tbody>
    </Table>
  );
});
