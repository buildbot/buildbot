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

import {
  Build,
  Buildset,
  Builder,
  Buildrequest,
  Change,
  DataCollection,
  UNKNOWN,
} from 'buildbot-data-js';

export const BRANCH_FILTER_ALL_TEXT = '(all)';

export type ChangeInfo = {
  change: Change;
  buildsets: Map<number, Buildset>;
};

export type BuilderInfo = {
  builder: Builder;
  buildsByChangeId: Map<number, Build[]>;
};

export function resolveGridData(
  buildsetsQuery: DataCollection<Buildset>,
  changesQuery: DataCollection<Change>,
  buildersQuery: DataCollection<Builder>,
  buildrequestsQuery: DataCollection<Buildrequest>,
  buildsQuery: DataCollection<Build>,
  branchesFilterText: string,
  resultsFilter: number,
  leftToRight: boolean,
  revisionLimit: number,
  shouldShowBuilder: (tags: string[]) => boolean,
): [string[], ChangeInfo[], BuilderInfo[]] {
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

    if (
      branchesFilterText !== BRANCH_FILTER_ALL_TEXT &&
      changeInfo.change.branch !== branchesFilterText
    ) {
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
        const builds = (buildsByBrid.get(br.buildrequestid) ?? []).filter(
          (b) => resultsFilter === UNKNOWN || b.results === resultsFilter,
        );

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
