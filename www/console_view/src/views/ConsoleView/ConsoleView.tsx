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

import './ConsoleView.scss'
import {ObservableMap} from "mobx";
import {observer, useLocalObservable} from "mobx-react";
import {Link} from "react-router-dom";
import {
  FaExclamationCircle,
  FaMinusCircle,
  FaPlusCircle
} from "react-icons/fa";
import {OverlayTrigger, Table, Tooltip} from "react-bootstrap";
import {buildbotGetSettings, buildbotSetupPlugin} from "buildbot-plugin-support";
import {
  Build,
  Buildset,
  Builder,
  Buildrequest,
  Change,
  useDataAccessor, useDataApiQuery, IDataAccessor
} from "buildbot-data-js";
import {
  BuildLinkWithSummaryTooltip,
  ChangeDetails,
  LoadingIndicator,
  pushIntoMapOfArrays,
  useWindowSize
} from "buildbot-ui";

type ChangeInfo = {
  change: Change;
  buildsByBuilderId: Map<number, Build[]>;
}

export type TagTreeItem = {
  builders: Builder[];
  tag: string;
  childItems: TagTreeItem[];
}

export type TagItemConfig = {
  tag: string,
  colSpan: number
};

export type TagLineConfig = TagItemConfig[];

export function buildTagTree(builders: Builder[])
{
  const buildersByTags = new Map<string, Builder[]>();
  for (const builder of builders) {
    if (builder.tags === null) {
      continue;
    }
    for (const tag of builder.tags) {
      pushIntoMapOfArrays(buildersByTags, tag, builder);
    }
  }

  type TagInfo = {
    tag: string;
    builders: Builder[];
  };

  const undecidedTags: TagInfo[] = [];
  for (const [tag, tagBuilders] of buildersByTags) {
    if (tagBuilders.length < builders.length) {
      undecidedTags.push({tag: tag, builders: tagBuilders});
    }
  }

  // sort the tags to first look at tags with the larger number of builders
  // @FIXME maybe this is not the best method to find the best groups
  undecidedTags.sort((a, b) => b.builders.length - a.builders.length);

  const tagItems: TagTreeItem[] = [];
  const builderIdToTag = new Map<number, string>();

  // pick the tags one by one, by making sure we make non-overalaping groups
  for (const tagInfo of undecidedTags) {
    let excluded = false;
    for (const builder of tagInfo.builders) {
      if (builderIdToTag.has(builder.builderid)) {
        excluded = true;
        break;
      }
    }
    if (!excluded) {
      for (const builder of tagInfo.builders) {
        builderIdToTag.set(builder.builderid, tagInfo.tag);
      }
      tagItems.push({tag: tagInfo.tag, builders: tagInfo.builders, childItems: []});
    }
  }

  // some builders do not have tags, we put them in another group
  const remainingBuilders = [];
  for (const builder of builders) {
    if (!builderIdToTag.has(builder.builderid)) {
      remainingBuilders.push(builder);
    }
  }

  if (remainingBuilders.length) {
    tagItems.push({tag: "", builders: remainingBuilders, childItems: []});
  }

  // if there is more than one tag in this line, we need to recurse
  if (tagItems.length > 1) {
    for (const tagItem of tagItems) {
      tagItem.childItems = buildTagTree(tagItem.builders);
    }
  }
  return tagItems;
}

// Sorts and groups builders together by their tags.
export function sortBuildersByTags(builders: Builder[]) : [Builder[], TagLineConfig[]]
{
  // we call recursive function, which finds non-overlapping groups
  const tagLineItems = buildTagTree(builders);

  // we get a tree of builders grouped by tags
  // we now need to flatten the tree, in order to build several lines of tags
  // (each line is representing a depth in the tag tree)
  // we walk the tree left to right and build the list of builders in the tree order, and the tag_lines
  // in the tree, there are groups of remaining builders, which could not be grouped together,
  // those have the empty tag ''
  const tagLineConfigAtDepth = new Map<number, TagLineConfig>();

  const resultBuilders: Builder[] = [];

  const setTagLine = (depth: number, tag: string, colSpan: number) => {
    const lineConfig = tagLineConfigAtDepth.get(depth);
    if (lineConfig === undefined) {
      tagLineConfigAtDepth.set(depth, [{tag: tag, colSpan: colSpan}]);
      return;
    }

    // Attempt to merge identical tags
    const lastItem = lineConfig[lineConfig.length - 1];
    if (lastItem.tag === tag) {
      lastItem.colSpan += colSpan;
      return;
    }
    lineConfig.push({tag: tag, colSpan: colSpan});
  };

  const walkItemTree = (tagItem: TagTreeItem, depth: number) => {
    setTagLine(depth, tagItem.tag, tagItem.builders.length);
    if (tagItem.childItems.length === 0) {
      // this is the leaf of the tree, sort by buildername, and add them to the
      // list of sorted builders
      tagItem.builders.sort((a, b) => a.name.localeCompare(b.name));

      resultBuilders.push(...tagItem.builders);

      for (let i = 1; i <= 100; i++) {
        // set the remaining depth of the tree to the same colspan
        // (we hardcode the maximum depth for now :/ )
        setTagLine(depth + i, '', tagItem.builders.length);
      }
      return;
    }
    tagItem.childItems.map(item => walkItemTree(item, depth + 1));
  };

  for (const tagItem of tagLineItems) {
    walkItemTree(tagItem, 0);
  }

  const resultTagLineConfigs: TagLineConfig[] = [];

  for (const tagLineItems of tagLineConfigAtDepth.values()) {
    if (tagLineItems.length === 1 && tagLineItems[0].tag === "") {
      continue;
    }
    resultTagLineConfigs.push(tagLineItems);
  }
  return [resultBuilders, resultTagLineConfigs];
}

function resolveFakeChange(codebase: string, revision: string, whenTimestamp: number,
                           changesByFakeId: Map<string, ChangeInfo>): ChangeInfo
{
  const fakeId = `${codebase}-${revision}`;
  const existingChange = changesByFakeId.get(fakeId);
  if (existingChange !== undefined) {
    return existingChange;
  }

  const newChange = {
    change: new Change(undefined as unknown as IDataAccessor, "a/1", {
      changeid: 0,
      author: "",
      branch: "",
      codebase: codebase,
      comments: `Unknown revision ${revision}`,
      files: [],
      parent_changeids: [],
      project: "",
      properties: {},
      repository: "",
      revision: revision,
      revlink: null,
      when_timestamp: whenTimestamp,
    }),
    buildsByBuilderId: new Map<number, Build[]>
  };
  changesByFakeId.set(fakeId, newChange);
  return newChange;
}

// Adjusts changesByFakeId for any new fake changes that are created
function selectChangeForBuild(build: Build, buildset: Buildset,
                              changesBySsid: Map<number, ChangeInfo>,
                              changesByRevision: Map<string, ChangeInfo>,
                              changesByFakeId: Map<string, ChangeInfo>) {
  if (buildset.sourcestamps !== null) {
    for (const sourcestamp of buildset.sourcestamps) {
      const change = changesBySsid.get(sourcestamp.ssid);
      if (change !== undefined) {
        return change;
      }
    }
  }

  if (build.properties !== null && ('got_revision' in build.properties)) {
    const revision = build.properties['got_revision'][0];
    // got_revision can be per codebase or just the revision string
    if (typeof(revision) === "string") {
      const change = changesByRevision.get(revision);
      if (change !== undefined) {
        return change;
      }

      return resolveFakeChange("", revision, build.started_at, changesByFakeId);
    }

    const revisionMap = revision as {[codebase: string]: string};
    for (const codebase in revisionMap) {
      const codebaseRevision = revisionMap[codebase];
      const change = changesByRevision.get(codebaseRevision);
      if (change !== undefined) {
        return change;
      }
    }

    const codebases = Object.keys(revisionMap);
    if (codebases.length === 0) {
      return resolveFakeChange("unknown codebase", "", build.started_at, changesByFakeId);
    }
    return resolveFakeChange(codebases[0], revisionMap[codebases[0]], build.started_at,
      changesByFakeId);
  }

  const revision = `unknown revision ${build.builderid}-${build.buildid}`;
  return resolveFakeChange("unknown codebase", revision, build.started_at, changesByFakeId);
}

export const ConsoleView = observer(() => {
  const accessor = useDataAccessor([]);

  const settings = buildbotGetSettings();
  const changeFetchLimit = settings.getIntegerSetting("Console.changeLimit");
  const buildFetchLimit = settings.getIntegerSetting("Console.buildLimit");

  const buildsetsQuery = useDataApiQuery(() => Buildset.getAll(accessor, {query: {
      limit: buildFetchLimit,
      order: '-submitted_at',
    }}));

  const changesQuery = useDataApiQuery(() => Change.getAll(accessor, {query: {
      limit: changeFetchLimit,
      order: '-changeid',
    }}));

  const buildersQuery = useDataApiQuery(() => Builder.getAll(accessor));

  const buildrequestsQuery = useDataApiQuery(() => Buildrequest.getAll(accessor, {query: {
      limit: buildFetchLimit,
      order: '-submitted_at',
    }}));

  const buildsQuery = useDataApiQuery(() => Build.getAll(accessor, {query: {
      limit: buildFetchLimit,
      order: '-started_at',
      property: ["got_revision"],
    }}));

  const windowSize = useWindowSize()
  const changeIsExpandedByChangeId = useLocalObservable(() => new ObservableMap<number, boolean>());

  const queriesResolved =
    buildsetsQuery.resolved &&
    changesQuery.resolved &&
    buildersQuery.resolved &&
    buildrequestsQuery.resolved &&
    buildsQuery.resolved;

  const builderIdsWithBuilds = new Set<number>();
  for (const build of buildsQuery.array) {
    builderIdsWithBuilds.add(build.builderid);
  }

  const buildersWithBuilds = buildersQuery.array.filter(b => builderIdsWithBuilds.has(b.builderid));
  const [buildersToShow, tagLineConfigs] = sortBuildersByTags(buildersWithBuilds);

  const changesByRevision = new Map<string, ChangeInfo>();
  const changesBySsid = new Map<number, ChangeInfo>();
  const changesByFakeId = new Map<string, ChangeInfo>();

  for (const change of changesQuery.array) {
    const changeInfo: ChangeInfo = {change: change, buildsByBuilderId: new Map<number, Build[]>()};
    if (change.revision !== null) {
      changesByRevision.set(change.revision, changeInfo);
    }
    changesBySsid.set(change.sourcestamp.ssid, changeInfo);
  }

  for (const build of buildsQuery.array) {
    if (build.buildrequestid === null) {
      continue;
    }
    const buildrequest = buildrequestsQuery.getByIdOrNull(build.buildrequestid.toString());
    if (buildrequest === null) {
      continue;
    }
    const buildset = buildsetsQuery.getByIdOrNull(buildrequest.buildsetid.toString());
    if (buildset === null) {
      continue;
    }

    const change = selectChangeForBuild(build, buildset, changesBySsid, changesByRevision,
      changesByFakeId);

    pushIntoMapOfArrays(change.buildsByBuilderId, build.builderid, build);
  }

  const changesToShow = [...changesBySsid.values(), ...changesByFakeId.values()]
    .filter(ch => ch.buildsByBuilderId.size > 0)
    .sort((a, b) => b.change.when_timestamp - a.change.when_timestamp);


  const hasExpandedChanges = [...changeIsExpandedByChangeId.values()].includes(true);

  // The magic value is selected so that the column holds 78 character lines without wrapping
  const rowHeaderWidth = hasExpandedChanges ? 400 : 200;

  // Determine if we use a 100% width table or if we allow horizontal scrollbar
  // Depending on number of builders, and size of window, we need a fixed column size or a
  // 100% width table
  const isBigTable = () => {
    const padding = rowHeaderWidth;
    if (((windowSize.width - padding) / buildersToShow.length) < 40) {
      return true;
    }
    return false;
  }

  const getColHeaderHeight = () => {
    let maxBuilderName = 0;
    for (const builder of buildersToShow) {
      maxBuilderName = Math.max(builder.name.length, maxBuilderName);
    }
    return Math.max(100, maxBuilderName * 3);
  }

  const openAllChanges = () => {
    for (const change of changesToShow) {
      changeIsExpandedByChangeId.set(change.change.changeid, true);
    }
  };

  const closeAllChanges = () => {
    for (const changeid of changeIsExpandedByChangeId.keys()) {
      changeIsExpandedByChangeId.set(changeid, false);
    }
  };

  // FIXME: fa-spin
  if (!queriesResolved) {
    return (
      <div className="bb-console-container">
        <LoadingIndicator/>
      </div>
    );
  }

  if (changesQuery.array.length === 0) {
    return (
      <div className="bb-console-container">
        <p>
          No changes. Console View needs a changesource to be setup,
          and <Link to="/changes">changes</Link> to be in the system.
        </p>
      </div>
    );
  }

  const builderColumns = buildersToShow.map(builder => {
    return (
      <th key={builder.name} className="column">
        <span style={{marginTop: getColHeaderHeight()}} className="bb-console-table-builder">
          <Link to={`/builders/${builder.builderid}`}>{builder.name}</Link>
        </span>
      </th>
    )
  });

  const tagLineRows = tagLineConfigs.map((tagLineConfig, i) => {
    const columns = tagLineConfig.map((item, i) => {
      return (
        <td key={i} colSpan={item.colSpan}>
          <span style={{width: item.colSpan * 50}}>{item.tag}</span>
        </td>
      );
    });

    return (
      <tr className="bb-console-tag-row" key={`tag-${i}`}>
        <td className="row-header"></td>
        {columns}
      </tr>
    )
  });

  const changeRows = changesToShow.map(changeInfo => {
    const change = changeInfo.change;

    const builderColumns = buildersToShow.map(builder => {
      const builds = changeInfo.buildsByBuilderId.get(builder.builderid) ?? [];
      const buildLinks = builds.map(build => (
        <BuildLinkWithSummaryTooltip key={build.buildid} build={build}/>
      ));

      return (
        <td key={builder.name} title={builder.name} className="column">
          {buildLinks}
        </td>
      );
    });

    // Note that changeid may not be unique because fake changes always have changeid of 0
    return (
      <tr key={`change-${change.changeid}-${change.codebase}-${change.revision ?? ''}`}>
        <td>
          <ChangeDetails change={change} compact={true}
                         showDetails={changeIsExpandedByChangeId.get(change.changeid) ?? false}
                         setShowDetails={(show: boolean) => changeIsExpandedByChangeId.set(change.changeid, show)}/>
        </td>
        {builderColumns}
      </tr>
    );
  });

  return (
    <div className="container bb-console">
      <Table striped bordered className={(isBigTable() ? 'table-fixedwidth' : '')}>
        <thead>
          <tr className="bb-console-table-first-row first-row">
            <th className="row-header" style={{width: rowHeaderWidth}}>
              <OverlayTrigger trigger="click" placement="top" overlay={
                <Tooltip id="bb-console-view-open-all-changes">
                  Open information for all changes
                </Tooltip>
              } rootClose={true}>
                <FaPlusCircle onClick={e => openAllChanges()} className="bb-console-changes-expand-icon clickable"/>
              </OverlayTrigger>

              <OverlayTrigger trigger="click" placement="top" overlay={
                <Tooltip id="bb-console-view-close-all-changes">
                  Close information for all changes
                </Tooltip>
              } rootClose={true}>
                <FaMinusCircle onClick={e => closeAllChanges()} className="bb-console-changes-expand-icon clickable"/>
              </OverlayTrigger>
            </th>
            {builderColumns}
          </tr>
        </thead>
        <tbody>
          {tagLineRows}
          {changeRows}
        </tbody>
      </Table>
    </div>
  );
});

buildbotSetupPlugin(reg => {
  reg.registerMenuGroup({
    name: 'console',
    caption: 'Console View',
    icon: <FaExclamationCircle/>,
    order: 5,
    route: '/console',
    parentName: null,
  });

  reg.registerRoute({
    route: "/console",
    group: "console",
    element: () => <ConsoleView/>,
  });

  reg.registerSettingGroup({
    name: "Console",
    caption: "Console related settings",
    items: [
      {
        type: 'integer',
        name: 'changeLimit',
        caption: 'Maximum number of changes to fetch',
        defaultValue: 30
      }, {
        type: 'integer',
        name: 'buildLimit',
        caption: 'Maximum number of builds to fetch',
        defaultValue: 200
      }
    ]
  });
});

export default ConsoleView;
