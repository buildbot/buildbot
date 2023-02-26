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

import {parseLogChunk} from "./LogChunkParsing";
import {findTextInChunkRaw, resultsListToLineIndexMap} from "./LogChunkSearch";

describe('LogChunkSearch', () => {
  describe('findTextInChunkRaw', () => {
    it('no escapes', () => {
      expect(findTextInChunkRaw(parseLogChunk(20, 'oaaa\nboaaabaaa\no\noaaab\n', 's'), 'aaa'))
        .toEqual([
          {lineIndex: 20, lineStart: 0},
          {lineIndex: 21, lineStart: 1},
          {lineIndex: 21, lineStart: 5},
          {lineIndex: 23, lineStart: 0},
        ]);
    });
    it('many escapes', () => {
      expect(findTextInChunkRaw(parseLogChunk(20,
          'oaaa\nboa\x1b[36maabaa\x1b[36ma\no\no\x1b[36maaa\x1b[36mb\n', 's', true), 'aaa'))
        .toEqual([
          {lineIndex: 20, lineStart: 0},
          {lineIndex: 21, lineStart: 1},
          {lineIndex: 21, lineStart: 5},
          {lineIndex: 23, lineStart: 0},
        ]);
    });
    it('some escapes', () => {
      expect(findTextInChunkRaw(parseLogChunk(20,
          'o\no\no\no\no\no\noaaa\nboa\x1b[36maabaa\x1b[36ma\no\no\x1b[36maaa\x1b[36mb\n', 's'),
          'aaa'))
        .toEqual([
          {lineIndex: 26, lineStart: 0},
          {lineIndex: 27, lineStart: 1},
          {lineIndex: 27, lineStart: 5},
          {lineIndex: 29, lineStart: 0},
        ]);
    });
  });

  function testResultsListToLineIndexMap(lineIndexes: number[], expected: Map<number, number>) {
    const results = lineIndexes.map(i => {return {lineIndex: i, lineStart: 0}});
    expect(resultsListToLineIndexMap(results)).toEqual(expected);
  };

  describe('resultsListToLineIndexMap', () => {
    it('empty', () => {
      testResultsListToLineIndexMap([], new Map<number, number>());
    });
    it('nonrepeating', () => {
      testResultsListToLineIndexMap([1, 2, 3, 10, 11, 12], new Map<number, number>([
        [1, 0],
        [2, 1],
        [3, 2],
        [10, 3],
        [11, 4],
        [12, 5],
      ]));
    });
    it('repeating', () => {
      testResultsListToLineIndexMap([1, 2, 3, 3, 3, 12], new Map<number, number>([
        [1, 0],
        [2, 1],
        [3, 2],
        [12, 5],
      ]));
    });
  });
});
