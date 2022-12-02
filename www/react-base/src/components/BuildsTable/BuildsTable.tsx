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

import './BuildsTable.scss';
import {observer} from "mobx-react";
import {Table} from "react-bootstrap";
import {Builder} from "../../data/classes/Builder";
import {Build} from "../../data/classes/Build";
import {dateFormat, durationFormat, durationFromNowFormat, useCurrentTime} from "../../util/Moment";
import DataCollection from "../../data/DataCollection";
import {Link} from "react-router-dom";
import {getPropertyValueArrayOrEmpty, getPropertyValueOrDefault} from "../../util/Properties";
import BuildLinkWithSummaryTooltip
  from "../BuildLinkWithSummaryTooltip/BuildLinkWithSummaryTooltip";
import TableHeading from "../TableHeading/TableHeading";

type BuildsTableProps = {
  builds: DataCollection<Build>;
  builders: DataCollection<Builder> | null;
}

const BuildsTable = observer(({builds, builders}: BuildsTableProps) => {
  const now = useCurrentTime();
  const sortedBuilds = builds.array.slice().sort((a, b) => b.started_at - a.started_at);

  const rowElements = sortedBuilds.map(build => {
    const builder = builders === null ? null : builders.getByIdOrNull(build.builderid.toString());
    const builderNameElement = builders === null
      ? <></>
      : <td>{builder === null ? "" : builder.name}</td>

    const buildCompleteInfoElement = build.complete
      ? (
        <span title={durationFormat(build.complete_at! - build.started_at)}>
          {durationFormat(build.complete_at! - build.started_at)}
        </span>
      )
      : <></>;

    return (
      <tr key={build.id}>
        {builderNameElement}
        <td>
          <BuildLinkWithSummaryTooltip build={build}/>
        </td>
        <td>
          <span title={dateFormat(build.started_at)}>
            {durationFromNowFormat(build.started_at, now)}
          </span>
        </td>
        <td>
          {buildCompleteInfoElement}
        </td>
        <td>{getPropertyValueArrayOrEmpty(build.properties, 'owners').map(owner => <span>{owner}</span>)}
        </td>
    <td>
      <Link to={`/workers/${build.workerid}`}>
        {getPropertyValueOrDefault(build.properties, 'workername', '(unknown)')}
      </Link>
    </td>
    <td>
      <ul className="list-inline">
        <li>{build.state_string}</li>
      </ul>
    </td>
  </tr>
    );
  });

  const tableElement = () => {
    return (
      <Table hover striped size="sm">
        <tbody>
          <tr>
            { builders !== null ? <td width="200px">Builder</td> : <></> }
            <td width="100px">#</td>
            <td width="150px">Started At</td>
            <td width="150px">Duration</td>
            <td width="200px">Owners</td>
            <td width="150px">Worker</td>
            <td>Status</td>
          </tr>
          {rowElements}
        </tbody>
      </Table>
    );
  }

  return (
    <div className="bb-build-table-container">
      <>
        <TableHeading>Builds:</TableHeading>
        { builds.array.length === 0 ? <span>None</span> : tableElement() }
      </>
    </div>
  );
});

export default BuildsTable;
