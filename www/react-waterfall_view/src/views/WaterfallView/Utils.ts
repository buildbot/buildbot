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

import {Build} from "buildbot-data-js";
import {pushIntoMapOfArrays} from "buildbot-ui";

export type BuildGroup = {
  minTime: number;
  maxTime: number;
}

export function groupBuildsPerBuilder(builds: Build[]) {
  const builderToBuilds = new Map<number, Build[]>();
  for (const build of builds) {
    pushIntoMapOfArrays(builderToBuilds, build.builderid, build);
  }
  return builderToBuilds;
}

export function groupBuildsByTime(builderIds: Set<number>, builds: Build[],
                                  threshold: number, currentTimeS: number) {
  const sortedBuilds = [...builds];
  // sort by time by sorting by buildid which always increases
  sortedBuilds.sort((a, b) => a.buildid - b.buildid);

  let maxCompleteTime = 0;

  const groups: BuildGroup[] = [];

  for (const build of sortedBuilds) {
    if (!builderIds.has(build.builderid)) {
      // filtered builder
      continue;
    }

    if ((build.started_at - maxCompleteTime) > threshold) {
      if (groups.length > 0) {
        groups[groups.length - 1].maxTime = maxCompleteTime;
      }
      groups.push({minTime: build.started_at, maxTime: build.started_at});
    }

    const buildEndTime = build.complete
      ? build.complete_at! : Math.max(build.started_at, currentTimeS);

    if (buildEndTime > maxCompleteTime) {
      maxCompleteTime = buildEndTime;
    }
  }

  if (groups.length > 0) {
    groups[groups.length - 1].maxTime = maxCompleteTime;
  }

  return groups;
}

export class WaterfallYScale {
  buildGroups: BuildGroup[];
  height = 0;
  heightNoGap = 0;
  gap = 0;
  totalGroupTimeSum = 0;

  constructor(buildGroups: BuildGroup[], gap: number, height: number) {
    this.buildGroups = buildGroups;
    this.height = height;
    this.heightNoGap = height - ((buildGroups.length - 1) * gap);
    this.gap = gap;

    this.totalGroupTimeSum = 0;
    for (const group of buildGroups) {
      this.totalGroupTimeSum += (group.maxTime - group.minTime);
    }
  }

  getCoord(time: number) {

    let groupTimeSum = 0;
    for (let id = 0; id < this.buildGroups.length; id++) {
      const group = this.buildGroups[id];
      if (group.minTime <= time && time <= group.maxTime) {
        groupTimeSum += time - group.minTime;
        return this.height - ((this.heightNoGap / this.totalGroupTimeSum) * groupTimeSum) -
          (id * this.gap);
      } else {
        groupTimeSum += group.maxTime - group.minTime;
      }
    }
    return undefined;
  }

  // coordinate to date
  invert(coordinate: number) {
    let groupTimeSum = 0;
    for (let id = 0; id < this.buildGroups.length; id++) {
      const group = this.buildGroups[id];

      const date = ((this.height - coordinate - (id * this.gap)) *
          (this.totalGroupTimeSum / this.heightNoGap)) -
        groupTimeSum + group.minTime;

      if (group.minTime <= date && date <= group.maxTime) {
        return date;
      }
      groupTimeSum += group.maxTime - group.minTime;
    }
    return undefined;
  }
}
