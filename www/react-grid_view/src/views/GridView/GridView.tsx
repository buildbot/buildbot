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
import {useState} from "react";
import {Link} from "react-router-dom";
import {FaCubes} from "react-icons/fa";
import {Form} from "react-bootstrap";
import {
  Build,
  Buildset,
  Builder,
  Buildrequest,
  Change,
  DataCollection,
  UNKNOWN,
  allResults,
  intToResultText,
  useDataAccessor,
  useDataApiQuery
} from "buildbot-data-js";
import {
  useTagFilterManager,
  BuildLinkWithSummaryTooltip,
  ChangeDetails,
  LoadingIndicator
} from "buildbot-ui";
import {buildbotGetSettings, buildbotSetupPlugin} from "buildbot-plugin-support";

const RESULT_FILTER_ALL_TEXT = "(all)";

const resultsOptions = new Map<string, number>();
resultsOptions.set(RESULT_FILTER_ALL_TEXT, UNKNOWN);
for (const result of allResults) {
  resultsOptions.set(intToResultText[result], result);
}

export const BRANCH_FILTER_ALL_TEXT = "(all)";

export type ChangeInfo = {
  change: Change;
  buildsets: Map<number, Buildset>;
};

export type BuilderInfo = {
  builder: Builder;
  buildsByChangeId: Map<number, Build[]>;
};

export function resolveGridData(buildsetsQuery: DataCollection<Buildset>,
                                changesQuery: DataCollection<Change>,
                                buildersQuery: DataCollection<Builder>,
                                buildrequestsQuery: DataCollection<Buildrequest>,
                                buildsQuery: DataCollection<Build>,
                                branchesFilterText: string,
                                resultsFilter: number,
                                leftToRight: boolean,
                                revisionLimit: number,
                                shouldShowBuilder: (tags: string[]) => boolean):
  [string[], ChangeInfo[], BuilderInfo[]] {

  const changesBySsid = new Map<number, ChangeInfo>();
  const branchesSet = new Set<string>();

  for (const change of changesQuery.array) {
    if (change.branch === null) {
      change.branch = 'master';
    }
    changesBySsid.set(change.sourcestamp.ssid, {change, buildsets: new Map<number, Buildset>()});
  }

  const changesToShow = new Map<number, ChangeInfo>();

  for (const buildset of buildsetsQuery.array) {
    if (buildset.sourcestamps.length === 0) {
      continue;
    }

    const lastSs = buildset.sourcestamps[buildset.sourcestamps.length - 1];
    const changeInfo = changesBySsid.get(lastSs.ssid);
    if (changeInfo === undefined) {
      continue;
    }
    changeInfo.buildsets.set(buildset.bsid, buildset);
    branchesSet.add(changeInfo.change.branch!);

    if (branchesFilterText !== BRANCH_FILTER_ALL_TEXT &&
      changeInfo.change.branch !== branchesFilterText) {
      continue;
    }

    changesToShow.set(changeInfo.change.changeid, changeInfo);
  }

  let changesToShowArray = [...changesToShow.values()];
  changesToShowArray.sort((a, b) => a.change.changeid - b.change.changeid);
  if (changesToShowArray.length > revisionLimit) {
    changesToShowArray = changesToShowArray.slice(changesToShowArray.length - revisionLimit);
  }

  if (!leftToRight) {
    changesToShowArray = changesToShowArray.reverse();
  }

  // FIXME: use something like react-select to avoid ambiguous option names
  const branchOptions = [BRANCH_FILTER_ALL_TEXT, ...branchesSet.keys()];
  branchOptions.sort((a, b) => a.localeCompare(b));

  const requestsByBsid = new Map<number, Buildrequest[]>();
  for (const br of buildrequestsQuery.array) {
    const brs = requestsByBsid.get(br.buildsetid);
    if (brs === undefined) {
      requestsByBsid.set(br.buildsetid, [br]);
    } else {
      brs.push(br);
    }
  }

  const buildsByBrid = new Map<number, Build[]>();
  for (const build of buildsQuery.array) {
    if (build.buildrequestid === null) {
      continue;
    }

    // Note that there may be multiple builds for a given request,
    // for example when a worker connection is lost.
    const builds = buildsByBrid.get(build.buildrequestid);
    if (builds === undefined) {
      buildsByBrid.set(build.buildrequestid, [build]);
    } else {
      builds.push(build);
    }
  }

  const buildersById = new Map<number, BuilderInfo>();

  // find builds for the selected changes and associate them to builders
  for (const change of changesToShowArray) {
    for (const buildset of change.buildsets.values()) {
      const requests = requestsByBsid.get(buildset.bsid);
      if (requests === undefined) {
        continue;
      }

      for (const br of requests) {
        const builds = (buildsByBrid.get(br.buildrequestid) ?? [])
          .filter(b => resultsFilter === UNKNOWN || b.results === resultsFilter);

        if (builds.length === 0) {
          continue;
        }

        const builder = buildersQuery.getByIdOrNull(builds[0].builderid.toString());
        if (builder === null || !shouldShowBuilder(builder.tags)) {
          continue;
        }

        const builderInfo = buildersById.get(builder.builderid);
        if (builderInfo === undefined) {
          buildersById.set(builder.builderid, {
            builder: builder,
            buildsByChangeId: new Map<number, Build[]>([[change.change.changeid, builds]]),
          });
        } else {
          builderInfo.buildsByChangeId.set(change.change.changeid, builds);
        }
      }
    }
  }

  const buildersToShowArray = [...buildersById.values()];
  buildersToShowArray.sort((a, b) => a.builder.name.localeCompare(b.builder.name));

  return [branchOptions, changesToShowArray, buildersToShowArray];
}

export const GridView = observer(() => {
  const accessor = useDataAccessor([]);

  const filterManager = useTagFilterManager("tags");

  const settings = buildbotGetSettings();
  const revisionLimit = settings.getIntegerSetting("Grid.revisionLimit");
  const changeFetchLimit = settings.getIntegerSetting("Grid.changeFetchLimit");
  const buildFetchLimit = settings.getIntegerSetting("Grid.buildFetchLimit");
  const fullChanges = settings.getBooleanSetting("Grid.fullChanges");
  const leftToRight = settings.getBooleanSetting("Grid.leftToRight");

  const [resultsFilterText, setResultsFilterText] = useState(RESULT_FILTER_ALL_TEXT);
  const [branchesFilterText, setBranchesFilterText] = useState(BRANCH_FILTER_ALL_TEXT);
  const resultsFilter = resultsOptions.get(resultsFilterText);

  const buildsetsQuery = useDataApiQuery(() => Buildset.getAll(accessor, {query: {
      limit: buildFetchLimit,
      order: '-bsid',
    }}));

  const changesQuery = useDataApiQuery(() => Change.getAll(accessor, {query: {
      limit: changeFetchLimit,
      order: '-changeid',
    }}));

  const buildersQuery = useDataApiQuery(() => Builder.getAll(accessor));

  const buildrequestsQuery = useDataApiQuery(() => Buildrequest.getAll(accessor, {query: {
      limit: buildFetchLimit,
      order: '-buildrequestid',
    }}));

  const buildsQuery = useDataApiQuery(() => Build.getAll(accessor, {query: {
      limit: buildFetchLimit,
      order: '-buildrequestid',
    }}));

  const queriesResolved =
    buildsetsQuery.resolved &&
    changesQuery.resolved &&
    buildersQuery.resolved &&
    buildrequestsQuery.resolved &&
    buildsQuery.resolved;

  // FIXME: fa-spin
  if (!queriesResolved) {
    return (
      <div className="bb-grid-container">
        <LoadingIndicator/>
      </div>
    );
  }

  if (changesQuery.array.length === 0) {
    return (
      <div className="bb-grid-container">
        <p>
          No changes. Grid View needs a changesource to be setup,
          and <Link to="/changes"> changes</Link> to be in the system.
        </p>
      </div>
    );
  }

  const [branchOptions, changesToShow, buildersToShow] = resolveGridData(
    buildsetsQuery, changesQuery, buildersQuery, buildrequestsQuery, buildsQuery,
    branchesFilterText, resultsFilter!, leftToRight, revisionLimit,
    tags => filterManager.shouldShowByTags(tags)
  );


  const changeColumns = changesToShow
      .slice()
      .sort((a, b) => b.change.changeid - a.change.changeid)
      .map(ch => {
    return (
      <th className="change">
        <ChangeDetails change={ch.change} compact={!fullChanges}
                       showDetails={false} setShowDetails={() => {}}/>
      </th>
    )
  });

  const builderRowElements = buildersToShow.map(builderInfo => {
    const builder = builderInfo.builder;
    const buildsByChangeId = builderInfo.buildsByChangeId;

    const changeColumnElements = changesToShow.map(changeInfo => {
      const change = changeInfo.change;
      const buildsForChange = [...(buildsByChangeId.get(change.changeid) ?? [])];
      buildsForChange.sort((a, b) => a.buildid - b.buildid);

      return (
        <td key={change.changeid}>
          {buildsForChange.map(build => (
            <BuildLinkWithSummaryTooltip key={build.id} build={build}/>
           ))
          }
        </td>
      );
    });

    return (
      <tr key={builder.name}>
        <th>
          <Link to={`/builders/${builder.builderid}`}>{builder.name}</Link>
        </th>
        <td>
          {filterManager.getElementsForTags(builder.tags)}
        </td>
        {changeColumnElements}
      </tr>
    );
  });

  return (
    <div className="container grid">
      <Form inline className="mb-sm-2">
        <Form.Label className="mr-sm-2">Branch</Form.Label>
        <Form.Control className="mr-sm-2" as="select" multiple={false} value={branchesFilterText}
                      onChange={event => setBranchesFilterText(event.target.value)}>
          {branchOptions.map(branch => (<option>{branch}</option>))}
        </Form.Control>
        <Form.Label className="mr-sm-2">Results</Form.Label>
        <Form.Control className="mr-sm-2" as="select" multiple={false} value={resultsFilterText}
                      onChange={event => setResultsFilterText(event.target.value)}>
          {[...resultsOptions.keys()].map(text => (<option>{text}</option>))}
        </Form.Control>
      </Form>
      <table className="table table-condensed table-striped table-hover">
        <thead>
        <tr>
          <th>Builder</th>
          <th>
            {filterManager.getFiltersHelpElement()}
            {filterManager.getEnabledFiltersElements()}
          </th>
          {changeColumns}
        </tr>
        </thead>
        <tbody>
          {builderRowElements}
        </tbody>
      </table>
    </div>
  );
});

buildbotSetupPlugin(reg => {
  reg.registerMenuGroup({
    name: 'grid',
    caption: 'Grid View',
    icon: <FaCubes/>,
    order: 4,
    route: '/grid',
    parentName: null,
  });

  reg.registerRoute({
    route: "/grid",
    group: "grid",
    element: () => <GridView/>,
  });

  reg.registerSettingGroup({
    name: "Grid",
    caption: "Grid related settings",
    items: [
      {
        type: 'boolean',
        name: 'fullChanges',
        caption: 'Show avatar and time ago in change details',
        defaultValue: false
      }, {
        type: 'boolean',
        name: 'leftToRight',
        caption: 'Show most recent changes on the right',
        defaultValue: false
      }, {
        type: 'integer',
        name: 'revisionLimit',
        caption: 'Maximum number of revisions to display',
        defaultValue: 5
      }, {
        type: 'integer',
        name: 'changeFetchLimit',
        caption: 'Maximum number of changes to fetch',
        defaultValue: 100
      }, {
        type: 'integer',
        name: 'buildFetchLimit',
        caption: 'Maximum number of builds to fetch',
        defaultValue: 1000
      }
    ]
  });
});

export default GridView;
