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

import {observer} from 'mobx-react';
import {useState} from 'react';
import {Link, useSearchParams} from 'react-router-dom';
import {FaCubes} from 'react-icons/fa';
import {Form} from 'react-bootstrap';
import {
  Build,
  Buildset,
  Builder,
  Buildrequest,
  Change,
  UNKNOWN,
  allResults,
  intToResultText,
  useDataAccessor,
  useDataApiQuery,
} from 'buildbot-data-js';
import {
  getBuildLinkDisplayProperties,
  useTagFilterManager,
  BuildLinkWithSummaryTooltip,
  ChangeDetails,
  LoadingIndicator,
} from 'buildbot-ui';
import {buildbotGetSettings, buildbotSetupPlugin} from 'buildbot-plugin-support';
import {BRANCH_FILTER_ALL_TEXT, resolveGridData} from './Utils';

const RESULT_FILTER_ALL_TEXT = '(all)';

const resultsOptions = new Map<string, number>();
resultsOptions.set(RESULT_FILTER_ALL_TEXT, UNKNOWN);
for (const result of allResults) {
  resultsOptions.set(intToResultText[result], result);
}

export const GridView = observer(() => {
  const accessor = useDataAccessor([]);

  const filterManager = useTagFilterManager('tags');

  const settings = buildbotGetSettings();
  const revisionLimit = settings.getIntegerSetting('Grid.revisionLimit');
  const changeFetchLimit = settings.getIntegerSetting('Grid.changeFetchLimit');
  const buildFetchLimit = settings.getIntegerSetting('Grid.buildFetchLimit');
  const fullChanges = settings.getBooleanSetting('Grid.fullChanges');
  const leftToRight = settings.getBooleanSetting('Grid.leftToRight');

  const [detailedChanges, setDetailedChanges] = useState<Set<string>>(() => new Set());
  const [resultsFilterText, setResultsFilterText] = useState(RESULT_FILTER_ALL_TEXT);
  const [searchParams, setSearchParams] = useSearchParams();
  const branchesFilterText = searchParams.get('branch') ?? BRANCH_FILTER_ALL_TEXT;
  const setBranchesFilterText = (branch: string) => {
    const newParams = new URLSearchParams([...searchParams.entries()]);
    if (branch === BRANCH_FILTER_ALL_TEXT) {
      newParams.delete('branch');
    } else {
      newParams.set('branch', branch);
    }
    setSearchParams(newParams);
  };
  const resultsFilter = resultsOptions.get(resultsFilterText);

  const buildsetsQuery = useDataApiQuery(() =>
    Buildset.getAll(accessor, {
      query: {
        limit: buildFetchLimit,
        order: '-bsid',
      },
    }),
  );

  const changesQuery = useDataApiQuery(() =>
    Change.getAll(accessor, {
      query: {
        limit: changeFetchLimit,
        order: '-changeid',
      },
    }),
  );

  const buildersQuery = useDataApiQuery(() => Builder.getAll(accessor));

  const buildrequestsQuery = useDataApiQuery(() =>
    Buildrequest.getAll(accessor, {
      query: {
        limit: buildFetchLimit,
        order: '-buildrequestid',
      },
    }),
  );

  const buildsQuery = useDataApiQuery(() =>
    Build.getAll(accessor, {
      query: {
        limit: buildFetchLimit,
        order: '-buildrequestid',
        property: getBuildLinkDisplayProperties(),
      },
    }),
  );

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
        <LoadingIndicator />
      </div>
    );
  }

  if (changesQuery.array.length === 0) {
    return (
      <div className="bb-grid-container">
        <p>
          No changes. Grid View needs a changesource to be setup, and{' '}
          <Link to="/changes"> changes</Link> to be in the system.
        </p>
      </div>
    );
  }

  const [branchOptions, changesToShow, buildersToShow] = resolveGridData(
    buildsetsQuery,
    changesQuery,
    buildersQuery,
    buildrequestsQuery,
    buildsQuery,
    branchesFilterText,
    resultsFilter!,
    leftToRight,
    revisionLimit,
    (tags) => filterManager.shouldShowByTags(tags),
  );

  const changeColumns = changesToShow
    .slice()
    .sort((a, b) => b.change.changeid - a.change.changeid)
    .map((ch) => {
      return (
        <th className="change">
          <ChangeDetails
            change={ch.change}
            compact={!fullChanges}
            showDetails={detailedChanges.has(ch.change.id)}
            setShowDetails={(show: boolean) => {
              setDetailedChanges((current) => {
                const updated = new Set(current);
                if (show) {
                  updated.add(ch.change.id);
                } else {
                  updated.delete(ch.change.id);
                }
                return updated;
              });
            }}
          />
        </th>
      );
    });

  const builderRowElements = buildersToShow.map((builderInfo) => {
    const builder = builderInfo.builder;
    const buildsByChangeId = builderInfo.buildsByChangeId;

    const changeColumnElements = changesToShow.map((changeInfo) => {
      const change = changeInfo.change;
      const buildsForChange = [...(buildsByChangeId.get(change.changeid) ?? [])];
      buildsForChange.sort((a, b) => a.buildid - b.buildid);

      return (
        <td key={change.changeid}>
          {buildsForChange.map((build) => (
            <BuildLinkWithSummaryTooltip key={build.id} build={build} />
          ))}
        </td>
      );
    });

    return (
      <tr key={builder.name}>
        <th>
          <Link to={`/builders/${builder.builderid}`}>{builder.name}</Link>
        </th>
        <td>{filterManager.getElementsForTags(builder.tags)}</td>
        {changeColumnElements}
      </tr>
    );
  });

  return (
    <div className="container grid">
      <Form className="mb-sm-2">
        <Form.Label className="mr-sm-2">Branch</Form.Label>
        <Form.Control
          className="mr-sm-2"
          as="select"
          multiple={false}
          value={branchesFilterText}
          onChange={(event) => setBranchesFilterText(event.target.value)}
        >
          {branchOptions.map((branch) => (
            <option>{branch}</option>
          ))}
        </Form.Control>
        <Form.Label className="mr-sm-2">Results</Form.Label>
        <Form.Control
          className="mr-sm-2"
          as="select"
          multiple={false}
          value={resultsFilterText}
          onChange={(event) => setResultsFilterText(event.target.value)}
        >
          {[...resultsOptions.keys()].map((text) => (
            <option>{text}</option>
          ))}
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
        <tbody>{builderRowElements}</tbody>
      </table>
    </div>
  );
});

buildbotSetupPlugin((reg) => {
  reg.registerMenuGroup({
    name: 'grid',
    caption: 'Grid View',
    icon: <FaCubes />,
    order: 4,
    route: '/grid',
    parentName: null,
  });

  reg.registerRoute({
    route: '/grid',
    group: 'grid',
    element: () => <GridView />,
  });

  reg.registerSettingGroup({
    name: 'Grid',
    caption: 'Grid related settings',
    items: [
      {
        type: 'boolean',
        name: 'fullChanges',
        caption: 'Show avatar and time ago in change details',
        defaultValue: false,
      },
      {
        type: 'boolean',
        name: 'leftToRight',
        caption: 'Show most recent changes on the right',
        defaultValue: false,
      },
      {
        type: 'integer',
        name: 'revisionLimit',
        caption: 'Maximum number of revisions to display',
        defaultValue: 5,
      },
      {
        type: 'integer',
        name: 'changeFetchLimit',
        caption: 'Maximum number of changes to fetch',
        defaultValue: 100,
      },
      {
        type: 'integer',
        name: 'buildFetchLimit',
        caption: 'Maximum number of builds to fetch',
        defaultValue: 1000,
      },
    ],
  });
});

export default GridView;
