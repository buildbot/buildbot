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
import {
  Build,
  Builder,
  DataCollection,
  getPropertyValueArrayOrEmpty,
  getPropertyValueOrDefault
} from "buildbot-data-js";
import {
  BuildLinkWithSummaryTooltip,
  buildDurationFormatWithLocks,
  dateFormat,
  durationFromNowFormat,
  useCurrentTime
} from "buildbot-ui";
import {Link} from "react-router-dom";
import {LoadingSpan} from "../LoadingSpan/LoadingSpan";
import {TableHeading} from "../TableHeading/TableHeading";
import {durationFormat} from "buildbot-ui";
import {buildbotGetSettings, buildbotSetupPlugin} from "../../../../plugin_support";
import {FaHome} from "react-icons/fa";
import {HomeView} from "../../views/HomeView/HomeView";

type BuildsTableProps = {
  builds: DataCollection<Build>;
  builders: DataCollection<Builder> | null;
}

const BUILD_TIME_BASE_START_TIME = 'Start time and duration';
const BUILD_TIME_BASE_COMPLETE_TIME = 'Completion time';

const getBuildTimeElement = (build: Build, buildTimeBase: string, now: number) =>
{
  if (buildTimeBase === BUILD_TIME_BASE_COMPLETE_TIME) {
    return build.complete ? (
        <span title={dateFormat(build.complete_at!)}>
          {dateFormat(build.complete_at!)}
        </span>
      ) : (
        <span title={dateFormat(build.started_at)}>
          Started at {dateFormat(build.started_at)}
        </span>
      );
  }
  return (
    <span title={dateFormat(build.started_at)}>
      {durationFromNowFormat(build.started_at, now)}
    </span>
  )
}

export const BuildsTable = observer(({builds, builders}: BuildsTableProps) => {
  const now = useCurrentTime();
  const sortedBuilds = builds.array.slice().sort((a, b) => b.started_at - a.started_at);

  const buildTimeBase = buildbotGetSettings().getChoiceComboSetting("BuildsTable.build_time_base");

  const rowElements = sortedBuilds.map(build => {
    const builder = builders === null ? null : builders.getByIdOrNull(build.builderid.toString());
    const builderNameElement = builders === null
      ? <></>
      : <td>{builder === null ? "" : builder.name}</td>

    const durationString = buildDurationFormatWithLocks(build, now);
    const buildCompleteInfoElement = build.complete
      ? <span title={durationString}>{durationString}</span>
      : <></>;

    return (
      <tr key={build.id}>
        {builderNameElement}
        <td>
          <BuildLinkWithSummaryTooltip build={build}/>
        </td>
        <td>
          {getBuildTimeElement(build, buildTimeBase, now)}
        </td>
        <td>
          {buildCompleteInfoElement}
        </td>
        <td>
          {getPropertyValueOrDefault(build.properties, "revision", "(unknown)")}
        </td>
        <td>{getPropertyValueArrayOrEmpty(build.properties, 'owners').map((owner, index) => (
          <span key={index}>{owner}</span>
        ))}
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
            <td width="150px">{buildTimeBase === BUILD_TIME_BASE_COMPLETE_TIME ? 'Completed At' : 'Started At'}</td>
            <td width="150px">Duration</td>
            <td width='150px'>Revision</td>
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
        { !builds.isResolved()
          ? <LoadingSpan/>
          : builds.array.length === 0
            ? <span>None</span>
            : tableElement() }
      </>
    </div>
  );
});

buildbotSetupPlugin((reg) => {
  reg.registerSettingGroup({
    name: 'BuildsTable',
    caption: 'Build tables related settings',
    items: [{
      type: 'choice_combo',
      name: 'build_time_base',
      caption: 'Build time information to display',
      choices: [BUILD_TIME_BASE_START_TIME, BUILD_TIME_BASE_COMPLETE_TIME],
      defaultValue: 'Start time and duration'
    }]});
});
