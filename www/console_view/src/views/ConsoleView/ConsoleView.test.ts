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

import {Builder, IDataAccessor} from "buildbot-data-js";
import {sortBuildersByTags, TagLineConfig} from "./ConsoleView";

type TestBuilder = {
  builderid: number;
  tags: string[];
}

function testBuilderToReal(b: TestBuilder) {
  return new Builder(undefined as unknown as IDataAccessor, 'a/1', {
    builderid: b.builderid,
    description: "desc",
    masterids: [1],
    name: `name${b.builderid}`,
    tags: b.tags,
  });
}

describe('ConsoleView', function() {
  describe('sortBuildersByTags', function() {

    function testSortBuildersByTags(builders: TestBuilder[],
                                    expectedBuilders: TestBuilder[],
                                    expectedTagLines: TagLineConfig[]) {
      const [resultBuilders, resultLineConfigs] =
        sortBuildersByTags(builders.map(b => testBuilderToReal(b)));

      expect(resultBuilders).toStrictEqual(expectedBuilders.map(b => testBuilderToReal(b)));
      expect(resultLineConfigs).toStrictEqual(expectedTagLines);
    }

    it('empty', function() {
      testSortBuildersByTags([], [], []);
    });

    it('identical tag', function() {
      testSortBuildersByTags([
        {builderid: 1, tags: ['tag']},
        {builderid: 2, tags: ['tag']},
        {builderid: 3, tags: ['tag']}
      ], [
        {builderid: 1, tags: ['tag']},
        {builderid: 2, tags: ['tag']},
        {builderid: 3, tags: ['tag']}
      ], []);
    });

    it('two tags', function() {
      testSortBuildersByTags([
        {builderid: 1, tags: ['tag']},
        {builderid: 2, tags: ['tag']},
        {builderid: 3, tags: ['tag']},
        {builderid: 4, tags: ['tag2']}
      ], [
        {builderid: 1, tags: ['tag']},
        {builderid: 2, tags: ['tag']},
        {builderid: 3, tags: ['tag']},
        {builderid: 4, tags: ['tag2']}
      ], [[{tag: 'tag', colSpan: 3}, {tag: 'tag2', colSpan: 1}]]);
    });

    it('hierarchical', function() {
      testSortBuildersByTags([
        {builderid: 1, tags: ['tag10', 'tag21']},
        {builderid: 2, tags: ['tag10', 'tag21']},
        {builderid: 3, tags: ['tag10', 'tag22']},
        {builderid: 4, tags: ['tag11', 'tag22']}
      ], [
        {builderid: 1, tags: ['tag10', 'tag21']},
        {builderid: 2, tags: ['tag10', 'tag21']},
        {builderid: 3, tags: ['tag10', 'tag22']},
        {builderid: 4, tags: ['tag11', 'tag22']},
      ], [
        [{tag: 'tag10', colSpan: 3}, {tag: 'tag11', colSpan: 1}],
        [{tag: 'tag21', colSpan: 2}, {tag: 'tag22', colSpan: 1}, {tag: "", colSpan: 1}],
      ]);
    });
  });
});
