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
  Builder,
  Buildrequest,
  Buildset,
  Change,
  MockDataCollection,
  IDataAccessor,
  SUCCESS, UNKNOWN, FAILURE,
} from "buildbot-data-js";
import {resolveGridData, BRANCH_FILTER_ALL_TEXT} from "./GridView";

type TestSourceStamp = {
  ssid: number,
  branch: string|null,
};

type TestBuildset = {
  bsid: number,
  sourcestamps: TestSourceStamp[],
  results: number|null,
};

type TestChange = {
  changeid: number,
  ssid: number,
  branch: string|null,
};

type TestBuilder = {
  builderid: number,
}

type TestBuildrequest = {
  buildrequestid: number,
  builderid: number,
  buildsetid: number,
  results: number|null,
}

type TestBuild = {
  buildid: number,
  builderid: number,
  buildrequestid: number,
  results: number|null,
}

type TestChangeInfo = {
  change: TestChange,
  buildsets: TestBuildset[],
};

type TestBuilderInfo = {
  builder: TestBuilder,
  builds: [number, TestBuild[]][];
};

function testBuildsetToReal(bs: TestBuildset) {
  return new Buildset(undefined as unknown as IDataAccessor, 'a/1', {
    bsid: bs.bsid,
    complete: false,
    complete_at: null,
    external_idstring: null,
    parent_buildid: null,
    parent_relationship: null,
    reason: 'reason',
    results: bs.results,
    sourcestamps: bs.sourcestamps.map(ss => ({
      ssid: ss.ssid,
      branch: ss.branch,
      codebase: "codebase",
      created_at: 123,
      patch: null,
      project: "project",
      repository: "repository",
      revision: "rev",
    })),
    submitted_at: 123
  });
};

function testChangeToReal(c: TestChange) {
  return new Change(undefined as unknown as IDataAccessor, 'a/1', {
    changeid: c.changeid,
    author: "author",
    branch: c.branch,
    category: "category",
    codebase: "codebase",
    comments: "comments",
    files: [],
    parent_changeids: [],
    project: "project",
    properties: {},
    repository: "repository",
    revision: null,
    revlink: null,
    sourcestamp: {
      ssid: c.ssid,
      branch: c.branch,
      codebase: "codebase",
      created_at: 123,
      patch: null,
      project: "project",
      repository: "repository",
      revision: null,
    },
    when_timestamp: 123,
  });
}

function testBuilderToReal(b: TestBuilder) {
  return new Builder(undefined as unknown as IDataAccessor, 'a/1', {
    builderid: b.builderid,
    description: "desc",
    masterids: [1],
    name: `name${b.builderid}`,
    tags: [],
  });
}

function testBuildrequestToReal(b: TestBuildrequest) {
  return new Buildrequest(undefined as unknown as IDataAccessor, 'a/1', {
    buildrequestid: b.buildrequestid,
    builderid: b.builderid,
    buildsetid: b.buildsetid,
    claimed: true,
    claimed_at: 123,
    claimed_by_masterid: 1,
    complete: false,
    complete_at: null,
    priority: 0,
    properties: {},
    results: b.results,
    submitted_at: 123,
    waited_for: false,
  });
}

function testBuildToReal(b: TestBuild) {
  return new Build(undefined as unknown as IDataAccessor, 'a/1', {
    buildid: b.buildid,
    buildrequestid: b.buildrequestid,
    builderid: b.builderid,
    number: 1,
    workerid: 2,
    masterid: 1,
    started_at: 123,
    complete_at: null,
    complete: false,
    state_string: "state",
    results: b.results,
    properties: {},
  });
}

describe('GridView', function() {
  function testDataResolving(buildsets: TestBuildset[],
                             changes: TestChange[],
                             builders: TestBuilder[],
                             buildrequests: TestBuildrequest[],
                             builds: TestBuild[],
                             branchFilter: string|null,
                             resultsFilter: number|null,
                             expectedBranches: string[],
                             expectedChangeInfo: TestChangeInfo[],
                             expectedBuilderInfo: TestBuilderInfo[]) {

    const buildsetsQuery = new MockDataCollection<Buildset>();
    buildsetsQuery.setItems(buildsets.map(bs => testBuildsetToReal(bs)));

    const changesQuery = new MockDataCollection<Change>();
    changesQuery.setItems(changes.map(ch => testChangeToReal(ch)));

    const buildersQuery = new MockDataCollection<Builder>();
    buildersQuery.setItems(builders.map(b => testBuilderToReal(b)));

    const buildrequestsQuery = new MockDataCollection<Buildrequest>();
    buildrequestsQuery.setItems(buildrequests.map(br => testBuildrequestToReal(br)));

    const buildsQuery = new MockDataCollection<Build>();
    buildsQuery.setItems(builds.map(b => testBuildToReal(b)));

    const [branches, changeInfos, builderInfos] = resolveGridData(
      buildsetsQuery, changesQuery, buildersQuery, buildrequestsQuery, buildsQuery,
      branchFilter === null ? BRANCH_FILTER_ALL_TEXT : branchFilter,
      resultsFilter === null ? UNKNOWN : resultsFilter,
      true, 10, tags => true);

    expect(branches).toEqual(expectedBranches);

    expect(changeInfos).toEqual(expectedChangeInfo.map(ch => ({
      change: testChangeToReal(ch.change),
      buildsets: new Map<number, Buildset>(ch.buildsets.map(bs => [
        bs.bsid,
        testBuildsetToReal(bs)
      ]))
    })));

    expect(builderInfos).toEqual(expectedBuilderInfo.map(builder => ({
      builder: testBuilderToReal(builder.builder),
      buildsByChangeId: new Map<number, Build[]>(builder.builds.map(changesToBuilds => [
        changesToBuilds[0],
        changesToBuilds[1].map(b => testBuildToReal(b)),
      ])),
    })));
  }

  describe('data resolving', () => {
    it('empty', () => {
      testDataResolving([], [], [], [], [], null, null, ["(all)"], [], []);
    });

    it('simple builds', () => {
      const buildsets: TestBuildset[] = [
        {
          bsid: 1,
          results: null,
          sourcestamps: [{
            ssid: 11,
            branch: "master",
          }],
        },
        {
          bsid: 2,
          results: null,
          sourcestamps: [{
            ssid: 12,
            branch: "other",
          }],
        }
      ];

      const changes: TestChange[] = [
        {changeid: 101, ssid: 11, branch: "master"},
        {changeid: 102, ssid: 12, branch: "other"},
        {changeid: 103, ssid: 13, branch: "no_builds"},
      ];

      const builders: TestBuilder[] = [
        {builderid: 201},
        {builderid: 202},
        {builderid: 203}, // not used by any builds
      ];

      const buildrequests: TestBuildrequest[] = [
        {buildrequestid: 301, builderid: 201, buildsetid: 1, results: SUCCESS},
        {buildrequestid: 302, builderid: 202, buildsetid: 1, results: null},
        {buildrequestid: 303, builderid: 201, buildsetid: 2, results: null},
        {buildrequestid: 304, builderid: 202, buildsetid: 2, results: SUCCESS},
      ];

      const builds: TestBuild[] = [
        {buildid: 401, buildrequestid: 301, builderid: 201, results: SUCCESS},
        {buildid: 402, buildrequestid: 302, builderid: 202, results: null},
        {buildid: 403, buildrequestid: 303, builderid: 201, results: null},
        {buildid: 404, buildrequestid: 304, builderid: 202, results: SUCCESS},
      ];

      testDataResolving(buildsets, changes, builders, buildrequests, builds, null, null,
        ["(all)", "master", "other"],
        [
          {
            change: {changeid: 101, ssid: 11, branch: "master"},
            buildsets: [
              {
                bsid: 1,
                results: null,
                sourcestamps: [{
                  ssid: 11,
                  branch: "master",
                }],
              }
            ]
          },
          {
            change: {changeid: 102, ssid: 12, branch: "other"},
            buildsets: [
              {
                bsid: 2,
                results: null,
                sourcestamps: [{
                  ssid: 12,
                  branch: "other",
                }],
              }
            ]
          }
        ], [
          {
            builder: {builderid: 201},
            builds: [
              [101, [{buildid: 401, buildrequestid: 301, builderid: 201, results: SUCCESS}]],
              [102, [{buildid: 403, buildrequestid: 303, builderid: 201, results: null}]],
            ],
          },
          {
            builder: {builderid: 202},
            builds: [
              [101, [{buildid: 402, buildrequestid: 302, builderid: 202, results: null}]],
              [102, [{buildid: 404, buildrequestid: 304, builderid: 202, results: SUCCESS}]],
            ],
          }
        ]
      );

      testDataResolving(buildsets, changes, builders, buildrequests, builds, "other", null,
        ["(all)", "master", "other"],
        [
          {
            change: {changeid: 102, ssid: 12, branch: "other"},
            buildsets: [
              {
                bsid: 2,
                results: null,
                sourcestamps: [{
                  ssid: 12,
                  branch: "other",
                }],
              }
            ]
          }
        ], [
          {
            builder: {builderid: 201},
            builds: [
              [102, [{buildid: 403, buildrequestid: 303, builderid: 201, results: null}]],
            ],
          },
          {
            builder: {builderid: 202},
            builds: [
              [102, [{buildid: 404, buildrequestid: 304, builderid: 202, results: SUCCESS}]],
            ],
          }
        ]
      );

      testDataResolving(buildsets, changes, builders, buildrequests, builds, "not_existing", null,
        ["(all)", "master", "other"], [], []);

      testDataResolving(buildsets, changes, builders, buildrequests, builds, null, SUCCESS,
        ["(all)", "master", "other"],
        [
          {
            change: {changeid: 101, ssid: 11, branch: "master"},
            buildsets: [
              {
                bsid: 1,
                results: null,
                sourcestamps: [{
                  ssid: 11,
                  branch: "master",
                }],
              }
            ]
          },
          {
            change: {changeid: 102, ssid: 12, branch: "other"},
            buildsets: [
              {
                bsid: 2,
                results: null,
                sourcestamps: [{
                  ssid: 12,
                  branch: "other",
                }],
              }
            ]
          }
        ], [
          {
            builder: {builderid: 201},
            builds: [
              [101, [{buildid: 401, buildrequestid: 301, builderid: 201, results: SUCCESS}]],
            ],
          },
          {
            builder: {builderid: 202},
            builds: [
              [102, [{buildid: 404, buildrequestid: 304, builderid: 202, results: SUCCESS}]],
            ],
          }
        ]
      );

      testDataResolving(buildsets, changes, builders, buildrequests, builds, null, FAILURE,
        ["(all)", "master", "other"], [
          {
            change: {changeid: 101, ssid: 11, branch: "master"},
            buildsets: [
              {
                bsid: 1,
                results: null,
                sourcestamps: [{
                  ssid: 11,
                  branch: "master",
                }],
              }
            ]
          },
          {
            change: {changeid: 102, ssid: 12, branch: "other"},
            buildsets: [
              {
                bsid: 2,
                results: null,
                sourcestamps: [{
                  ssid: 12,
                  branch: "other",
                }],
              }
            ]
          }
        ], []);

      testDataResolving(buildsets, changes, builders, buildrequests, builds, "other", FAILURE,
        ["(all)", "master", "other"], [
          {
            change: {changeid: 102, ssid: 12, branch: "other"},
            buildsets: [
              {
                bsid: 2,
                results: null,
                sourcestamps: [{
                  ssid: 12,
                  branch: "other",
                }],
              }
            ]
          }
        ], []);
    });
  });
});
