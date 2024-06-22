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
import {observer} from "mobx-react";
import {Link} from "react-router-dom";
import {
  BadgeRound,
  dateFormat,
  durationFromNowFormat,
  useCurrentTime
} from "buildbot-ui";
import {
  Buildrequest,
  DataCollection,
  getPropertyValueArrayOrEmpty,
  getPropertyValueOrDefault
} from "buildbot-data-js";

type BuildRequestsTableProps = {
  buildrequests: DataCollection<Buildrequest>;
}

export const BuildRequestsTable = observer(({buildrequests}: BuildRequestsTableProps) => {
  const now = useCurrentTime();
  const tableElement = () => {

    const sortedBuildrequests = buildrequests.array.slice()
      .sort((a, b) => {
        const byPriority = a.priority - b.priority;
        if (byPriority !== 0) {
          return byPriority;
        }
        return a.submitted_at - b.submitted_at;
      });

    const rowElements = sortedBuildrequests.filter(br => !br.claimed).map(br => {
      const owners = [
        getPropertyValueOrDefault(br.properties, "owner", null),
        ...getPropertyValueArrayOrEmpty(br.properties, "owners")
      ];

      const ownerElements = owners.filter(o => o !== null).map(owner => <span>{owner}</span>);

      return (
        <tr key={br.buildrequestid}>
          <td>
            <Link to={`/buildrequests/${br.buildrequestid}`}>
              <BadgeRound className=''>{br.buildrequestid.toString()}</BadgeRound>
            </Link>
          </td>
          <td>
            {br.priority}
          </td>
          <td>
            <span title={dateFormat(br.submitted_at)}>
              {durationFromNowFormat(br.submitted_at, now)}
            </span>
          </td>
          <td>
            {ownerElements}
          </td>
          <td></td>
        </tr>
      );
    });

    return (
      <Table hover striped size="sm">
        <tbody>
          <tr>
            <td width="100px">#</td>
            <td width="100px">Priority</td>
            <td width="150px">Submitted At</td>
            <td width="150px">Owners</td>
            <td>Properties</td>
          </tr>
          {rowElements}
        </tbody>
      </Table>
    );
  }

  return buildrequests.array.length === 0 ? <span>None</span> : tableElement();
});
