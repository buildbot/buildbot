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
import {Builder} from "../../data/classes/Builder";
import {globalMenuSettings} from "../../plugins/GlobalMenuSettings";
import {globalRoutes} from "../../plugins/GlobalRoutes";
import {Link} from "react-router-dom";
import {globalSettings} from "../../plugins/GlobalSettings";
import {Buildrequest} from "../../data/classes/Buildrequest";
import {dateFormat, durationFromNowFormat, useCurrentTime} from "../../util/Moment";
import {getPropertyValueOrDefault} from "../../util/Properties";
import BadgeRound from "../../components/BadgeRound/BadgeRound";
import TableHeading from "../../components/TableHeading/TableHeading";

const PendingBuildRequestsView = observer(() => {
  const now = useCurrentTime();
  const accessor = useDataAccessor([]);

  const buildRequestFetchLimit = globalSettings.getIntegerSetting("BuildRequests.buildrequestFetchLimit");
  const buildRequestsQuery = useDataApiQuery(
    () => Buildrequest.getAll(accessor, {query: {
      limit: buildRequestFetchLimit,
      order: '-submitted_at',
      claimed: false
    }}));

  const propertiesQuery = useDataApiQuery(() =>
    buildRequestsQuery.getRelatedProperties(br => br.getProperties()));
  const buildersQuery = useDataApiQuery(() =>
    buildRequestsQuery.getRelated(br => Builder.getAll(accessor, {id: br.builderid.toString()})));

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
        <tr key={buildRequest.id}>
          <td>
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

  const renderContents = () => {
    if (!buildRequestsQuery.resolved) {
      return <span>Loading ...</span>
    }
    if (buildRequestsQuery.array.length === 0) {
      return <span>None</span>
    }

    return (
      <Table hover striped size="sm">
        <tbody>
          <tr>
            <td width="100px">#</td>
            <td width="150px">Builder</td>
            <td width="150px">Submitted At</td>
            <td width="150px">Owner</td>
            <td width="150px">Properties</td>
          </tr>
          {renderBuildRequests()}
        </tbody>
      </Table>
    )
  }

  return (
    <div className="container">
      <TableHeading>Pending Buildrequests:</TableHeading>
      {renderContents()}
    </div>
  );
});


globalMenuSettings.addGroup({
  name: 'pendingbuildrequests',
  parentName: 'builds',
  caption: 'Pending Buildrequests',
  icon: null,
  order: null,
  route: '/pendingbuildrequests',
});

globalRoutes.addRoute({
  route: "pendingbuildrequests",
  group: "builds",
  element: () => <PendingBuildRequestsView/>,
});

globalSettings.addGroup({
  name: 'BuildRequests',
  caption: 'Buildrequests page related settings',
  items: [{
    type: 'integer',
    name: 'buildrequestFetchLimit',
    caption: 'Maximum number of pending buildrequests to fetch',
    defaultValue: 50
  }]});

export default PendingBuildRequestsView;
