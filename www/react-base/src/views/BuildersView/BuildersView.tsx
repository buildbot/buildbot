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

import './BuildersView.scss';
import {observer} from "mobx-react";
import {useState} from "react";
import {FaCogs} from "react-icons/fa";
import {buildbotGetSettings, buildbotSetupPlugin} from "buildbot-plugin-support";
import {
  Build,
  Builder,
  DataCollection,
  Master,
  Worker,
  useDataAccessor,
  useDataApiDynamicQuery,
  useDataApiQuery
} from "buildbot-data-js";
import {Link} from "react-router-dom";
import {
  BuildLinkWithSummaryTooltip,
  WorkerBadge,
  TagFilterManager,
  hasActiveMaster,
  useTagFilterManager,
  useTopbarItems,
} from "buildbot-ui";
import {computed} from "mobx";
import {Table} from "react-bootstrap";

const isBuilderFiltered = (builder: Builder, filterManager: TagFilterManager,
                           masters: DataCollection<Master>, showOldBuilders: boolean) => {
  if (!showOldBuilders && !hasActiveMaster(builder, masters)) {
    return false;
  }
  return filterManager.shouldShowByTags(builder.tags);
};

export const BuildersView = observer(() => {
  const accessor = useDataAccessor([]);

  const filterManager = useTagFilterManager("tags");
  const [builderNameFilter, setBuilderNameFilter] = useState("");

  useTopbarItems([
    {caption: "Builders", route: "/builders"}
  ]);

  const showOldBuilders = buildbotGetSettings().getBooleanSetting("Builders.show_old_builders");
  const showWorkerName = buildbotGetSettings().getBooleanSetting("Builders.show_workers_name");
  const buildFetchLimit = buildbotGetSettings().getIntegerSetting("Builders.buildFetchLimit");
  const perBuilderBuildFetchLimit = 15;

  // as there is usually lots of builders, its better to get the overall
  // list of workers, masters, and builds and then associate by builder
  const builders = useDataApiQuery(() => Builder.getAll(accessor));
  const masters = useDataApiQuery(() => Master.getAll(accessor));
  const workers = useDataApiQuery(() => Worker.getAll(accessor));

  const filteredBuilders = builders.array.filter(builder => {
    return isBuilderFiltered(builder, filterManager, masters, showOldBuilders) &&
      (builderNameFilter === null || builder.name.indexOf(builderNameFilter) >= 0)
  }).sort((a, b) => a.name.localeCompare(b.name));

  const filteredBuilderIds = filteredBuilders.map(builder => builder.builderid);

  const buildsForFilteredBuilders = useDataApiDynamicQuery(filteredBuilderIds,
    () => {
      // Don't request builds when we haven't loaded builders yet
      if (filteredBuilderIds.length === 0) {
        return new DataCollection<Build>();
      }
      return Build.getAll(accessor, {query: {
          limit: buildFetchLimit,
          order: '-started_at',
          builderid__eq: filteredBuilderIds,
          property: 'branch',
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
    for (const worker of workers.array) {
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

  const builderRowElements = filteredBuilders.map(builder => {

    let buildElements: JSX.Element[] = [];
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
        <td style={{width: "20%"}}>
          {filterManager.getElementsForTags(builder.tags)}
        </td>
        <td style={{width: "20%"}}>
          {workerElements}
        </td>
      </tr>
    );
  });

  // FIXME: implement pagination
  return (
    <div className="bb-builders-view-container">
      <form role="search" style={{width: "150px"}}>
        <input type="text" value={builderNameFilter}
               onChange={e => setBuilderNameFilter(e.target.value)}
               placeholder="Search for builders" className="bb-builders-view-form-control"/>
      </form>
      <Table hover striped size="sm">
        <tbody>
          <tr>
            <th>Builder Name</th>
            <th>Builds</th>
            <th>
              {filterManager.getFiltersHelpElement()}
              {filterManager.getEnabledFiltersElements()}
            </th>
            <th style={{width: "20%px"}}>Workers</th>
          </tr>
          {builderRowElements}
        </tbody>
      </Table>
      <div>
        <div className="form-group">
          <label className="checkbox-inline">
            <input type="checkbox" name="Show old builders"
                   checked={showOldBuilders}
                   onChange={event => {
                     buildbotGetSettings().setSetting("Builders.show_old_builders",
                       event.target.checked);
                     buildbotGetSettings().save();
                   }}/>
            {' '}Show old builders
          </label>
        </div>
      </div>
    </div>
  );
});

buildbotSetupPlugin((reg) => {
  reg.registerMenuGroup({
    name: 'builds',
    parentName: null,
    caption: 'Builds',
    icon: <FaCogs/>,
    order: 10,
    route: null,
  });

  reg.registerMenuGroup({
    name: 'builders',
    parentName: 'builds',
    caption: 'Builders',
    order: null,
    route: '/builders',
  });

  reg.registerRoute({
    route: "builders",
    group: "builders",
    element: () => <BuildersView/>,
  });

  reg.registerSettingGroup({
    name: 'Builders',
    caption: 'Builders page related settings',
    items: [{
      type: 'boolean',
      name: 'show_old_builders',
      caption: 'Show old builders',
      defaultValue: false
    }, {
      type: 'boolean',
      name: 'show_workers_name',
      caption: 'Show workers name',
      defaultValue: false
    }, {
      type: 'integer',
      name: 'buildFetchLimit',
      caption: 'Maximum number of builds to fetch',
      defaultValue: 200
    }, {
      type:'integer',
      name:'page_size',
      caption:'Number of builders to show per page',
      defaultValue: 100
    }
  ]});
});
