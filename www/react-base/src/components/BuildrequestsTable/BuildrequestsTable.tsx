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
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import {observer} from "mobx-react";
import {dateFormat, durationFromNowFormat, useCurrentTime} from "../../util/Moment";
import DataCollection from "../../data/DataCollection";
import {Link} from "react-router-dom";
import {getPropertyValueArrayOrEmpty, getPropertyValueOrDefault} from "../../util/Properties";
import {Buildrequest} from "../../data/classes/Buildrequest";
import BadgeRound from "../BadgeRound/BadgeRound";

type BuildRequestsTableProps = {
  buildrequests: DataCollection<Buildrequest>;
}

const BuildRequestsTable = observer(({buildrequests}: BuildRequestsTableProps) => {
  const now = useCurrentTime();
  const tableElement = () => {

    const sortedBuildrequests = buildrequests.array.slice()
      .sort((a, b) => a.submitted_at - b.submitted_at);

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
            <td width="150px">Submitted At</td>
            <td width="150px">Owners</td>
            <td>Properties</td>
          </tr>
          {rowElements}
        </tbody>
      </Table>
    );
  }

  return (
    <div>
      <Tabs defaultActiveKey={1}>
        <Tab eventKey={1} title="Build requests">
          {buildrequests.array.length === 0 ? <span>None</span> : tableElement()}
        </Tab>
      </Tabs>
    </div>
  )
});

export default BuildRequestsTable;
