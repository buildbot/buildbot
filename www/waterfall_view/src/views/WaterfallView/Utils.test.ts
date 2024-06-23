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

import {describe, expect, it} from "vitest";
import {Build, IDataAccessor, UNKNOWN} from "buildbot-data-js";
import {BuildGroup, groupBuildsByTime, WaterfallYScale} from "./Utils";

type TestBuild = {
  buildid: number;
  builderid: number;
  started_at: number;
  complete: boolean;
  complete_at: number|null;
}


function testBuildToReal(b: TestBuild) {
  return new Build(undefined as unknown as IDataAccessor, 'a/1', {
    buildid: b.buildid,
    buildrequestid: 100,
    builderid: b.builderid,
    number: 1,
    workerid: 2,
    masterid: 1,
    started_at: b.started_at,
    complete_at: b.complete_at,
    complete: b.complete,
    state_string: "state",
    results: UNKNOWN,
    properties: {},
  });
}

describe('Utils', () => {
  describe('groupBuildsByTime', () => {
    function testGroupBuildsByTime(builds: TestBuild[],
                                   builderIds: number[],
                                   threshold: number,
                                   currentTimeMs: number,
                                   expectedGroups: BuildGroup[]) {

      const groups = groupBuildsByTime(
        new Set<number>(builderIds), builds.map(b => testBuildToReal(b)),
        threshold, currentTimeMs);

      expect(groups).toStrictEqual(expectedGroups);
    }

    it('empty', () => {
      testGroupBuildsByTime([], [], 1000, 123400, []);
    });

    it('builds interleaving', () => {
      const builds: TestBuild[] = [
        {buildid: 1, builderid: 1, started_at: 90000, complete: true, complete_at: 90200},
        {buildid: 2, builderid: 1, started_at: 90100, complete: true, complete_at: 90300},
        {buildid: 3, builderid: 1, started_at: 90200, complete: true, complete_at: 90400},
        {buildid: 4, builderid: 1, started_at: 90300, complete: true, complete_at: 90500},
        {buildid: 5, builderid: 1, started_at: 90400, complete: true, complete_at: 90600},
      ];
      testGroupBuildsByTime(builds, [1], 1000, 123400, [{minTime: 90000, maxTime: 90600}]);
    });

    it('builds nearby', () => {
      const builds: TestBuild[] = [
        {buildid: 1, builderid: 1, started_at: 90000, complete: true, complete_at: 90100},
        {buildid: 2, builderid: 1, started_at: 90100, complete: true, complete_at: 90200},
        {buildid: 3, builderid: 1, started_at: 90200, complete: true, complete_at: 90300},
        {buildid: 4, builderid: 1, started_at: 90300, complete: true, complete_at: 90400},
        {buildid: 5, builderid: 1, started_at: 90400, complete: true, complete_at: 90500},
      ];
      testGroupBuildsByTime(builds, [1], 1000, 123400, [{minTime: 90000, maxTime: 90500}]);
    });

    it('builds small distance', () => {
      const builds: TestBuild[] = [
        {buildid: 1, builderid: 1, started_at: 90000, complete: true, complete_at: 90090},
        {buildid: 2, builderid: 1, started_at: 90100, complete: true, complete_at: 90190},
        {buildid: 3, builderid: 1, started_at: 90200, complete: true, complete_at: 90290},
        {buildid: 4, builderid: 1, started_at: 90300, complete: true, complete_at: 90390},
        {buildid: 5, builderid: 1, started_at: 90400, complete: true, complete_at: 90490},
      ];
      testGroupBuildsByTime(builds, [1], 1000, 123400, [{minTime: 90000, maxTime: 90490}]);
    });

    it('builds small distance, two groups', () => {
      const builds: TestBuild[] = [
        {buildid: 1, builderid: 1, started_at: 90000, complete: true, complete_at: 90090},
        {buildid: 2, builderid: 1, started_at: 90100, complete: true, complete_at: 90190},
        {buildid: 3, builderid: 1, started_at: 90200, complete: true, complete_at: 90290},
        {buildid: 4, builderid: 1, started_at: 90400, complete: true, complete_at: 90490},
        {buildid: 5, builderid: 1, started_at: 90500, complete: true, complete_at: 90590},
      ];
      testGroupBuildsByTime(builds, [1], 100, 123400, [
        {minTime: 90000, maxTime: 90290},
        {minTime: 90400, maxTime: 90590}
      ]);
    });

    it('builds unfinished', () => {
      const builds: TestBuild[] = [
        {buildid: 1, builderid: 1, started_at: 90000, complete: true, complete_at: 90090},
        {buildid: 2, builderid: 1, started_at: 90100, complete: true, complete_at: 90190},
        {buildid: 3, builderid: 1, started_at: 90200, complete: true, complete_at: 90290},
        {buildid: 4, builderid: 1, started_at: 90400, complete: true, complete_at: 90490},
        {buildid: 5, builderid: 1, started_at: 90500, complete: false, complete_at: null},
      ];
      testGroupBuildsByTime(builds, [1], 100, 123400, [
        {minTime: 90000, maxTime: 90290},
        {minTime: 90400, maxTime: 123400}
      ]);
    });

    it('builds unfinished, not last', () => {
      const builds: TestBuild[] = [
        {buildid: 1, builderid: 1, started_at: 90000, complete: true, complete_at: 90090},
        {buildid: 2, builderid: 1, started_at: 90100, complete: true, complete_at: 90190},
        {buildid: 3, builderid: 1, started_at: 90200, complete: true, complete_at: 90290},
        {buildid: 4, builderid: 1, started_at: 90400, complete: false, complete_at: null},
        {buildid: 5, builderid: 1, started_at: 90500, complete: true, complete_at: 90590},
      ];
      testGroupBuildsByTime(builds, [1], 100, 123400, [
        {minTime: 90000, maxTime: 90290},
        {minTime: 90400, maxTime: 123400}
      ]);
    });

    it('builds unfinished, not last group', () => {
      const builds: TestBuild[] = [
        {buildid: 1, builderid: 1, started_at: 90000, complete: true, complete_at: 90090},
        {buildid: 2, builderid: 1, started_at: 90100, complete: true, complete_at: 90190},
        {buildid: 3, builderid: 1, started_at: 90200, complete: false, complete_at: null},
        {buildid: 4, builderid: 1, started_at: 90400, complete: true, complete_at: 90490},
        {buildid: 5, builderid: 1, started_at: 90500, complete: true, complete_at: 90590},
      ];
      testGroupBuildsByTime(builds, [1], 100, 123400, [
        {minTime: 90000, maxTime: 123400}
      ]);
    });
  });

  describe('WaterfallYScale', () => {
    it('empty', () => {
      const scale = new WaterfallYScale([], 10, 100);
      expect(scale.getCoord(0)).toBeUndefined();
      expect(scale.getCoord(10)).toBeUndefined();
      expect(scale.invert(0)).toBeUndefined();
      expect(scale.invert(10)).toBeUndefined();
    });

    it('single group', () => {
      const scale = new WaterfallYScale([{minTime: 1000, maxTime: 1100}], 10, 200);
      expect(scale.getCoord(0)).toBeUndefined();
      expect(scale.getCoord(1000)).toEqual(200);
      expect(scale.getCoord(1050)).toEqual(100);
      expect(scale.getCoord(1100)).toEqual(0);
      expect(scale.getCoord(1101)).toBeUndefined();
      expect(scale.invert(201)).toBeUndefined();
      expect(scale.invert(200)).toEqual(1000);
      expect(scale.invert(100)).toEqual(1050);
      expect(scale.invert(0)).toEqual(1100);
      expect(scale.invert(-1)).toBeUndefined();
    });

    it('two groups', () => {
      const scale = new WaterfallYScale([
        {minTime: 1000, maxTime: 1100},
        {minTime: 1200, maxTime: 1300}
      ], 10, 410);
      expect(scale.getCoord(0)).toBeUndefined();
      expect(scale.getCoord(1000)).toEqual(410);
      expect(scale.getCoord(1050)).toEqual(310);
      expect(scale.getCoord(1100)).toEqual(210);
      expect(scale.getCoord(1101)).toBeUndefined();
      expect(scale.getCoord(1199)).toBeUndefined();
      expect(scale.getCoord(1200)).toEqual(200);
      expect(scale.getCoord(1250)).toEqual(100);
      expect(scale.getCoord(1300)).toEqual(0);
      expect(scale.getCoord(1301)).toBeUndefined();
      expect(scale.invert(411)).toBeUndefined();
      expect(scale.invert(410)).toEqual(1000);
      expect(scale.invert(310)).toEqual(1050);
      expect(scale.invert(210)).toEqual(1100);
      expect(scale.invert(209)).toBeUndefined();
      expect(scale.invert(201)).toBeUndefined();
      expect(scale.invert(200)).toEqual(1200);
      expect(scale.invert(100)).toEqual(1250);
      expect(scale.invert(0)).toEqual(1300);
      expect(scale.invert(-1)).toBeUndefined();
    });
  });
});
