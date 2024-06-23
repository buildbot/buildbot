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
import {parseLogChunk} from "./LogChunkParsing";
import {
  ChunkSearchResults, findNextSearchResult, findPrevSearchResult,
  findTextInChunkRaw,
  overlaySearchResultsOnLine,
  resultsListToLineIndexMap,
  getMatcher,
} from "./LogChunkSearch";

describe('LogChunkSearch', () => {
  function createChunkSearchResults(resultCounts: number[]) {
    return resultCounts.map(count => {
      const results: ChunkSearchResults = {
        results: [],
        lineIndexToFirstChunkIndex: new Map<number, number>()
      };
      for (let i = 0; i < count; ++i) {
        results.results.push({lineIndex: 0, lineStart: 0, lineEnd: 0});
      }
      return results;
    });
  }

  describe('findNextSearchResult', () => {
    it('no results', () => {
      expect(findNextSearchResult(createChunkSearchResults([]), 0, 0)).toEqual([-1, -1]);
    });

    it('out of bounds', () => {
      expect(findNextSearchResult(createChunkSearchResults([3, 3]), 5, 10)).toEqual([-1, -1]);
      expect(findNextSearchResult(createChunkSearchResults([3, 3]), -5, 10)).toEqual([-1, -1]);
    });

    it('single result', () => {
      expect(findNextSearchResult(createChunkSearchResults([0, 0, 1]), 2, 0)).toEqual([2, 0]);
      expect(findNextSearchResult(createChunkSearchResults([1, 0, 0]), 0, 0)).toEqual([0, 0]);
    });

    it('multiple results', () => {
      expect(findNextSearchResult(createChunkSearchResults([3, 3, 3]), 0, 0)).toEqual([0, 1]);
      expect(findNextSearchResult(createChunkSearchResults([3, 3, 3]), 0, 1)).toEqual([0, 2]);
      expect(findNextSearchResult(createChunkSearchResults([3, 3, 3]), 0, 2)).toEqual([1, 0]);
      expect(findNextSearchResult(createChunkSearchResults([3, 3, 3]), 1, 0)).toEqual([1, 1]);
      expect(findNextSearchResult(createChunkSearchResults([3, 3, 3]), 1, 1)).toEqual([1, 2]);
      expect(findNextSearchResult(createChunkSearchResults([3, 3, 3]), 1, 2)).toEqual([2, 0]);
      expect(findNextSearchResult(createChunkSearchResults([3, 3, 3]), 2, 0)).toEqual([2, 1]);
      expect(findNextSearchResult(createChunkSearchResults([3, 3, 3]), 2, 1)).toEqual([2, 2]);
      expect(findNextSearchResult(createChunkSearchResults([3, 3, 3]), 2, 2)).toEqual([0, 0]);

      expect(findNextSearchResult(createChunkSearchResults([0, 3, 3, 3, 0]), 1, 0)).toEqual([1, 1]);
      expect(findNextSearchResult(createChunkSearchResults([0, 3, 3, 3, 0]), 1, 1)).toEqual([1, 2]);
      expect(findNextSearchResult(createChunkSearchResults([0, 3, 3, 3, 0]), 1, 2)).toEqual([2, 0]);
      expect(findNextSearchResult(createChunkSearchResults([0, 3, 3, 3, 0]), 2, 0)).toEqual([2, 1]);
      expect(findNextSearchResult(createChunkSearchResults([0, 3, 3, 3, 0]), 2, 1)).toEqual([2, 2]);
      expect(findNextSearchResult(createChunkSearchResults([0, 3, 3, 3, 0]), 2, 2)).toEqual([3, 0]);
      expect(findNextSearchResult(createChunkSearchResults([0, 3, 3, 3, 0]), 3, 0)).toEqual([3, 1]);
      expect(findNextSearchResult(createChunkSearchResults([0, 3, 3, 3, 0]), 3, 1)).toEqual([3, 2]);
      expect(findNextSearchResult(createChunkSearchResults([0, 3, 3, 3, 0]), 3, 2)).toEqual([1, 0]);
    });
  });

  describe('findPrevSearchResult', () => {
    it('no results', () => {
      expect(findPrevSearchResult(createChunkSearchResults([]), 0, 0)).toEqual([-1, -1]);
    });

    it('out of bounds', () => {
      expect(findPrevSearchResult(createChunkSearchResults([3, 3]), 5, 10)).toEqual([-1, -1]);
      expect(findPrevSearchResult(createChunkSearchResults([3, 3]), -5, 10)).toEqual([-1, -1]);
    });

    it('single result', () => {
      expect(findPrevSearchResult(createChunkSearchResults([0, 0, 1]), 2, 0)).toEqual([2, 0]);
      expect(findPrevSearchResult(createChunkSearchResults([1, 0, 0]), 0, 0)).toEqual([0, 0]);
    });

    it('multiple results', () => {
      expect(findPrevSearchResult(createChunkSearchResults([3, 3, 3]), 0, 0)).toEqual([2, 2]);
      expect(findPrevSearchResult(createChunkSearchResults([3, 3, 3]), 0, 1)).toEqual([0, 0]);
      expect(findPrevSearchResult(createChunkSearchResults([3, 3, 3]), 0, 2)).toEqual([0, 1]);
      expect(findPrevSearchResult(createChunkSearchResults([3, 3, 3]), 1, 0)).toEqual([0, 2]);
      expect(findPrevSearchResult(createChunkSearchResults([3, 3, 3]), 1, 1)).toEqual([1, 0]);
      expect(findPrevSearchResult(createChunkSearchResults([3, 3, 3]), 1, 2)).toEqual([1, 1]);
      expect(findPrevSearchResult(createChunkSearchResults([3, 3, 3]), 2, 0)).toEqual([1, 2]);
      expect(findPrevSearchResult(createChunkSearchResults([3, 3, 3]), 2, 1)).toEqual([2, 0]);
      expect(findPrevSearchResult(createChunkSearchResults([3, 3, 3]), 2, 2)).toEqual([2, 1]);

      expect(findPrevSearchResult(createChunkSearchResults([0, 3, 3, 3, 0]), 1, 0)).toEqual([3, 2]);
      expect(findPrevSearchResult(createChunkSearchResults([0, 3, 3, 3, 0]), 1, 1)).toEqual([1, 0]);
      expect(findPrevSearchResult(createChunkSearchResults([0, 3, 3, 3, 0]), 1, 2)).toEqual([1, 1]);
      expect(findPrevSearchResult(createChunkSearchResults([0, 3, 3, 3, 0]), 2, 0)).toEqual([1, 2]);
      expect(findPrevSearchResult(createChunkSearchResults([0, 3, 3, 3, 0]), 2, 1)).toEqual([2, 0]);
      expect(findPrevSearchResult(createChunkSearchResults([0, 3, 3, 3, 0]), 2, 2)).toEqual([2, 1]);
      expect(findPrevSearchResult(createChunkSearchResults([0, 3, 3, 3, 0]), 3, 0)).toEqual([2, 2]);
      expect(findPrevSearchResult(createChunkSearchResults([0, 3, 3, 3, 0]), 3, 1)).toEqual([3, 0]);
      expect(findPrevSearchResult(createChunkSearchResults([0, 3, 3, 3, 0]), 3, 2)).toEqual([3, 1]);
    });
  });

  describe('findTextInChunkRaw', () => {
    it('no escapes', () => {
      expect(findTextInChunkRaw(parseLogChunk(20, 'oaaa\nboaaabaaa\no\noaaab\n', 's'), getMatcher('aaa')))
        .toEqual([
          {lineIndex: 20, lineStart: 0, lineEnd: 3},
          {lineIndex: 21, lineStart: 1, lineEnd: 4},
          {lineIndex: 21, lineStart: 5, lineEnd: 8},
          {lineIndex: 23, lineStart: 0, lineEnd: 3},
        ]);
    });
    it('many escapes', () => {
      expect(findTextInChunkRaw(parseLogChunk(20,
          'oaaa\nboa\x1b[36maabaa\x1b[36ma\no\no\x1b[36maaa\x1b[36mb\n', 's', true), getMatcher('aaa')))
        .toEqual([
          {lineIndex: 20, lineStart: 0, lineEnd: 3},
          {lineIndex: 21, lineStart: 1, lineEnd: 4},
          {lineIndex: 21, lineStart: 5, lineEnd: 8},
          {lineIndex: 23, lineStart: 0, lineEnd: 3},
        ]);
    });
    it('some escapes', () => {
      expect(findTextInChunkRaw(parseLogChunk(20,
          'o\no\no\no\no\no\noaaa\nboa\x1b[36maabaa\x1b[36ma\no\no\x1b[36maaa\x1b[36mb\n', 's'),
          getMatcher('aaa')))
        .toEqual([
          {lineIndex: 26, lineStart: 0, lineEnd: 3},
          {lineIndex: 27, lineStart: 1, lineEnd: 4},
          {lineIndex: 27, lineStart: 5, lineEnd: 8},
          {lineIndex: 29, lineStart: 0, lineEnd: 3},
        ]);
    });
    it('case insensitive', () => {
      expect(findTextInChunkRaw(parseLogChunk(20,
          'o\no\no\no\no\no\noaaa\nboa\x1b[36maabaa\x1b[36ma\no\no\x1b[36maaa\x1b[36mb\n', 's'),
          getMatcher('aAa', {caseInsensitive: true})))
        .toEqual([
          {lineIndex: 26, lineStart: 0, lineEnd: 3},
          {lineIndex: 27, lineStart: 1, lineEnd: 4},
          {lineIndex: 27, lineStart: 5, lineEnd: 8},
          {lineIndex: 29, lineStart: 0, lineEnd: 3},
        ]);
    });
    it('use regex', () => {
      expect(findTextInChunkRaw(parseLogChunk(20, 'oaaa\nboaaabaaa\no\noaaab\n', 's'), getMatcher('a+', {useRegex: true})))
        .toEqual([
          {lineIndex: 20, lineStart: 0, lineEnd: 3},
          {lineIndex: 21, lineStart: 1, lineEnd: 4},
          {lineIndex: 21, lineStart: 5, lineEnd: 8},
          {lineIndex: 23, lineStart: 0, lineEnd: 3},
        ]);
    });
    it('use regex with empty match', () => {
      expect(findTextInChunkRaw(parseLogChunk(20, 'oaaa\nboaaabaaa\no\noaaab\n', 's'), getMatcher('a*', {useRegex: true})))
        .toEqual([
          {lineIndex: 20, lineStart: 0, lineEnd: 3},
          {lineIndex: 21, lineStart: 1, lineEnd: 4},
          {lineIndex: 21, lineStart: 5, lineEnd: 8},
          {lineIndex: 23, lineStart: 0, lineEnd: 3},
        ]);
    });
  });

  function testResultsListToLineIndexMap(lineIndexes: number[], expected: Map<number, number>) {
    const results = lineIndexes.map(i => {return {lineIndex: i, lineStart: 0, lineEnd: 1}});
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

  describe('overlaySearchResultsOnLine', () => {
    it('unstyled', () => {
      expect(overlaySearchResultsOnLine({
        results: [{lineIndex: 10, lineStart: 5, lineEnd: 6}],
        lineIndexToFirstChunkIndex: new Map<number, number>([[10, 0]]),
      }, 10, 20, null, "b", "m", "e")).toEqual([
        {firstPos: 0, lastPos: 5, cssClasses: ""},
        {firstPos: 5, lastPos: 6, cssClasses: "m b e"},
        {firstPos: 6, lastPos: 20, cssClasses: ""},
      ]);
      expect(overlaySearchResultsOnLine({
        results: [{lineIndex: 10, lineStart: 5, lineEnd: 7}],
        lineIndexToFirstChunkIndex: new Map<number, number>([[10, 0]]),
      }, 10, 20, null, "b", "m", "e")).toEqual([
        {firstPos: 0, lastPos: 5, cssClasses: ""},
        {firstPos: 5, lastPos: 6, cssClasses: "m b"},
        {firstPos: 6, lastPos: 7, cssClasses: "m e"},
        {firstPos: 7, lastPos: 20, cssClasses: ""},
      ]);
      expect(overlaySearchResultsOnLine({
        results: [{lineIndex: 10, lineStart: 5, lineEnd: 8}],
        lineIndexToFirstChunkIndex: new Map<number, number>([[10, 0]]),
      }, 10, 20, null, "b", "m", "e")).toEqual([
        {firstPos: 0, lastPos: 5, cssClasses: ""},
        {firstPos: 5, lastPos: 6, cssClasses: "m b"},
        {firstPos: 6, lastPos: 7, cssClasses: "m"},
        {firstPos: 7, lastPos: 8, cssClasses: "m e"},
        {firstPos: 8, lastPos: 20, cssClasses: ""},
      ]);
    });
    it('styled', () => {
      expect(overlaySearchResultsOnLine({
        results: [{lineIndex: 10, lineStart: 5, lineEnd: 6}],
        lineIndexToFirstChunkIndex: new Map<number, number>([[10, 0]]),
      }, 10, 20, [
        {firstPos: 0, lastPos: 20, cssClasses: "u"},
      ], "b", "m", "e")).toEqual([
        {firstPos: 0, lastPos: 5, cssClasses: "u"},
        {firstPos: 5, lastPos: 6, cssClasses: "u m b e"},
        {firstPos: 6, lastPos: 20, cssClasses: "u"},
      ]);
      expect(overlaySearchResultsOnLine({
        results: [{lineIndex: 10, lineStart: 5, lineEnd: 7}],
        lineIndexToFirstChunkIndex: new Map<number, number>([[10, 0]]),
      }, 10, 20, [
        {firstPos: 0, lastPos: 20, cssClasses: "u"},
      ], "b", "m", "e")).toEqual([
        {firstPos: 0, lastPos: 5, cssClasses: "u"},
        {firstPos: 5, lastPos: 6, cssClasses: "u m b"},
        {firstPos: 6, lastPos: 7, cssClasses: "u m e"},
        {firstPos: 7, lastPos: 20, cssClasses: "u"},
      ]);
      expect(overlaySearchResultsOnLine({
        results: [{lineIndex: 10, lineStart: 5, lineEnd: 8}],
        lineIndexToFirstChunkIndex: new Map<number, number>([[10, 0]]),
      }, 10, 20, [
        {firstPos: 0, lastPos: 20, cssClasses: "u"},
      ], "b", "m", "e")).toEqual([
        {firstPos: 0, lastPos: 5, cssClasses: "u"},
        {firstPos: 5, lastPos: 6, cssClasses: "u m b"},
        {firstPos: 6, lastPos: 7, cssClasses: "u m"},
        {firstPos: 7, lastPos: 8, cssClasses: "u m e"},
        {firstPos: 8, lastPos: 20, cssClasses: "u"},
      ]);
    });
  });
});
