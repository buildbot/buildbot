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
import {buildbotGetSettings} from "buildbot-plugin-support";
import {
  Build,
  Builder,
  DataCollection,
  Master,
  Worker,
  useDataAccessor,
  useDataApiDynamicQuery,
} from "buildbot-data-js";
import {Link} from "react-router-dom";
import {
  getBuildLinkDisplayProperties,
  BuildLinkWithSummaryTooltip,
  WorkerBadge,
  TagFilterManager,
} from "buildbot-ui";
import {computed} from "mobx";
import {Table} from "react-bootstrap";
import {LoadingSpan} from "../LoadingSpan/LoadingSpan";

export type BuildersTableProps = {
  builders: Builder[];
  isLoading: boolean;
  allWorkers: DataCollection<Worker>;
  filterManager: TagFilterManager;
};

export const BuildersTable = observer(
    ({builders, allWorkers, isLoading, filterManager}: BuildersTableProps) => {
  const accessor = useDataAccessor([]);

  const showWorkerName= buildbotGetSettings().getBooleanSetting("Builders.show_workers_name");
  const buildFetchLimit= buildbotGetSettings().getIntegerSetting("Builders.buildFetchLimit");
  const perBuilderBuildFetchLimit = 15;

  const builderIds = builders.map(builder => builder.builderid);

  const buildsForFilteredBuilders = useDataApiDynamicQuery(builderIds,
      () => {
        // Don't request builds when we haven't loaded builders yet
        if (builderIds.length === 0) {
          return new DataCollection<Build>();
        }
        return Build.getAll(accessor, {query: {
            limit: buildFetchLimit,
            order: '-started_at',
            builderid__eq: builderIds,
            property: ['branch', ...getBuildLinkDisplayProperties()],
          }})
      });

  const buildsByFilteredBuilder = computed(() => {
    const byBuilderId: {[builderid: string]: Build[]} = {};
    for (const build of buildsForFilteredBuilders.array) {
      const builderid = build.builderid.toString();
      if (builderid in byBuilderId) {
        byBuilderId[builderid].push(build);
      } else {
        byBuilderId[builderid] = [build];
      }
    }
    return byBuilderId;
  }).get();

  const workersByFilteredBuilder = computed(() => {
    const byBuilderId: {[builderid: string]: Worker[]} = {};
    for (const worker of allWorkers.array) {
      for (const configured_on of worker.configured_on) {
        const builderid = configured_on.builderid.toString();
        if (builderid in byBuilderId) {
          byBuilderId[builderid].push(worker);
        } else {
          byBuilderId[builderid] = [worker];
        }
      }
    }
    return byBuilderId;
  }).get();

  const builderRowElements = builders.map(builder => {

    let buildElements: JSX.Element[] = [];
    if (!buildsForFilteredBuilders.isResolved()) {
      buildElements = [
        <LoadingSpan/>
      ];
    }

    if (builder.id in buildsByFilteredBuilder) {
      let builds = [...buildsByFilteredBuilder[builder.id]];
      builds = builds
          .sort((a, b) => b.number - a.number)
          .slice(0, perBuilderBuildFetchLimit);

      buildElements = builds.map(build => (<BuildLinkWithSummaryTooltip key={build.id} build={build}/>));
    }

    let workerElements: JSX.Element[] = [];
    if (builder.id in workersByFilteredBuilder) {
      let workers = [...workersByFilteredBuilder[builder.id]];
      workers.sort((a, b) => a.name.localeCompare(b.name));
      workerElements = workers.map(worker => (
          <WorkerBadge key={worker.name} worker={worker} showWorkerName={showWorkerName}/>
      ));
    }

    return (
        <tr key={builder.name}>
          <td style={{width: "200px"}}>
            <Link to={`/builders/${builder.builderid}`}>{builder.name}</Link></td>
          <td>
            {buildElements}
          </td>
          <td>
            {filterManager.getElementsForTags(builder.tags)}
          </td>
          <td>
            {workerElements}
          </td>
        </tr>
    );
  });

  if (builderRowElements.length === 0) {
    const noBuildersText = isLoading ? <LoadingSpan/> : "No builders to show";
    builderRowElements.push(
        <tr>
          <td colSpan={4}>{noBuildersText}</td>
        </tr>
    );
  }
  // FIXME: implement pagination
  return (
    <Table hover striped size="sm">
      <tbody>
      <tr>
        <th>Builder Name</th>
        <th>Builds</th>
        <th style={{maxWidth: "20%", minWidth: "70px"}}>
          {filterManager.getFiltersHelpElement()}
          {filterManager.getEnabledFiltersElements()}
        </th>
        <th style={{width: "20%"}}>Workers</th>
      </tr>
      {builderRowElements}
      </tbody>
    </Table>
  );
});
