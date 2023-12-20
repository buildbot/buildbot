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

import {stripLineEscapeCodes} from "./AnsiEscapeCodes";
import {binarySearchGreater} from "./BinarySearch";
import {addOverlayToCssClasses, combineCssClasses, LineCssClasses} from "./LineCssClasses";
import {ParsedLogChunk} from "./LogChunkParsing";
import {regexEscape} from "./Regex";

export type ChunkSearchOptions = {
  caseInsensitive?: boolean;
  useRegex?: boolean;
};

export type ChunkSearchResult = {
  // Global line index
  lineIndex: number;
  // The location of the found search string occurrence
  lineStart: number;
  lineEnd: number;
};

export type ChunkSearchResults = {
  results: ChunkSearchResult[];
  lineIndexToFirstChunkIndex: Map<number, number>;
};

export type MatchInfo = {pos: number, length: number};
export type MatcherFn = (text: string, pos?: number) => MatchInfo | null;

// Search options require the use of a regex
// Keep the indexOf path for simple search as it's more efficient
export function getMatcher(searchString: string, options?: ChunkSearchOptions): MatcherFn {
  if (options === undefined || (
    options.caseInsensitive !== true &&
    options.useRegex !== true
  )) {
    return (text: string, pos?: number) => {
      const foundPos = text.indexOf(searchString, pos ?? 0);
      return foundPos >= 0 ? {pos: foundPos, length: searchString.length} : null;
    };
  }

  const searchStringRegex = new RegExp(
    (options?.useRegex ? searchString : regexEscape(searchString)),
    (
      "g" +
      (options?.caseInsensitive ? "i" : "") +
      (options?.useRegex ? "m" : "")
    ),
  );
  return (text: string, pos?: number) => {
    searchStringRegex.lastIndex = pos ?? 0;
    let match = searchStringRegex.exec(text);
    // regex search such as 'a*' can result in a match that is empty
    // this is not interesting in our case, skip to the next relevant match
    while (match !== null && match[0].length <= 0) {
      searchStringRegex.lastIndex += 1;
      match = searchStringRegex.exec(text);
    }
    return match !== null ? {pos: match.index, length: match[0].length} : null;
  };
}

function findNextNonEmptyChunkSearchResults(results: ChunkSearchResults[], index: number) {
  for (let i = index; i < results.length; ++i) {
    if (results[i].results.length > 0) {
      return i;
    }
  }
  return -1;
}

// Returns a tuple of chunk index and index in chunk
export function findNextSearchResult(results: ChunkSearchResults[],
                                     chunkIndex: number, indexInChunk: number): [number, number] {
  if (chunkIndex < 0 || chunkIndex >= results.length) {
    return [-1, -1];
  }
  if (indexInChunk + 1 < results[chunkIndex].results.length) {
    return [chunkIndex, indexInChunk + 1];
  }

  chunkIndex = findNextNonEmptyChunkSearchResults(results, chunkIndex + 1);
  if (chunkIndex < 0) {
    chunkIndex = findNextNonEmptyChunkSearchResults(results, 0);
    if (chunkIndex < 0) {
      return [-1, -1];
    }
  }
  return [chunkIndex, 0];
}

function findPrevNonEmptyChunkSearchResults(results: ChunkSearchResults[], index: number) {
  for (let i = index; i >= 0; --i) {
    if (results[i].results.length > 0) {
      return i;
    }
  }
  return -1;
}

export function findPrevSearchResult(results: ChunkSearchResults[],
                                     chunkIndex: number, indexInChunk: number): [number, number] {
  if (chunkIndex < 0 || chunkIndex >= results.length) {
    return [-1, -1];
  }
  if (indexInChunk > 0) {
    return [chunkIndex, indexInChunk - 1];
  }
  chunkIndex = findPrevNonEmptyChunkSearchResults(results, chunkIndex - 1);
  if (chunkIndex < 0) {
    chunkIndex = findPrevNonEmptyChunkSearchResults(results, results.length - 1);
    if (chunkIndex < 0) {
      return [-1, -1];
    }
  }
  return [chunkIndex, results[chunkIndex].results.length - 1];
}

export function resultsListToLineIndexMap(results: ChunkSearchResult[]) : Map<number, number> {
  const indexMap = new Map<number, number>();
  if (results.length === 0) {
    return indexMap;
  }
  indexMap.set(results[0].lineIndex, 0);
  let prevLineIndex = results[0].lineIndex;
  for (let i = 1; i < results.length; ++i) {
    const lineIndex = results[i].lineIndex;
    if (lineIndex !== prevLineIndex) {
      indexMap.set(lineIndex, i);
      prevLineIndex = lineIndex;
    }
  }
  return indexMap;
}

function maybeAdvanceLineIndexToBound(lineIndex: number, pos: number, lineBounds: number[]) {
  if (pos < lineBounds[lineIndex + 1]) {
    return lineIndex;
  }
  lineIndex++;
  // Don't do binary search right away, the wanted index may be several lines away
  for (let i = 0; i < 3; ++i) {
    if (pos < lineBounds[lineIndex + 1]) {
      return lineIndex;
    }
    lineIndex++;
  }

  return binarySearchGreater(lineBounds, pos, undefined, lineIndex) - 1;
}

function findTextInLine(results: ChunkSearchResult[], text: string, lineIndex: number,
                        matcherFn: MatcherFn) {

  let match = matcherFn(text);
  while (match !== null) {
    results.push({
      lineIndex: lineIndex,
      lineStart: match.pos,
      lineEnd: match.pos + match.length,
    });
    match = matcherFn(text, match.pos + match.length);
  }
}

export function findTextInChunkRaw(chunk: ParsedLogChunk,
                                   matcherFn: MatcherFn): ChunkSearchResult[] {
  const searchNoPerLineEscapes =
    chunk.linesWithEscapes === null || chunk.linesWithEscapes.length === 0;

  if (searchNoPerLineEscapes) {
    const text = chunk.textNoEscapes !== null ? chunk.textNoEscapes : chunk.text;
    const lineBounds = chunk.textNoEscapesLineBounds !== null
      ? chunk.textNoEscapesLineBounds : chunk.textLineBounds;

    const results: ChunkSearchResult[] = [];
    let lineIndex = 0;
    let match = matcherFn(text);
    while (match !== null) {
      lineIndex = maybeAdvanceLineIndexToBound(lineIndex, match.pos, lineBounds);
      results.push({
        lineIndex: lineIndex + chunk.firstLine,
        lineStart: match.pos - lineBounds[lineIndex],
        lineEnd: (match.pos - lineBounds[lineIndex]) + match.length,
      });
      match = matcherFn(text, match.pos + match.length);
    }
    return results;
  }

  // Hybrid search by searching text without escape sequences and handling lines with escape
  // sequences as a special case.

  const text = chunk.text;
  const lineBounds = chunk.textLineBounds;
  const linesWithEscapes = chunk.linesWithEscapes!;

  const results: ChunkSearchResult[] = [];
  let lineIndex = 0;
  let linesWithEscapesIndex = 0;

  let match = matcherFn(text);
  while (match !== null) {
    lineIndex = maybeAdvanceLineIndexToBound(lineIndex, match.pos, lineBounds);

    if (linesWithEscapesIndex < linesWithEscapes.length) {
      if (lineIndex === linesWithEscapes[linesWithEscapesIndex]) {
        // Skip results from escaped line
        match = matcherFn(text, match.pos + match.length);
        continue;
      }
      if (lineIndex > linesWithEscapes[linesWithEscapesIndex]) {
        // Add results from any skipped escaped lines.
        while (linesWithEscapesIndex < linesWithEscapes.length &&
            lineIndex > linesWithEscapes[linesWithEscapesIndex]) {
          const escapedLineIndex = linesWithEscapes[linesWithEscapesIndex];
          const line = text.slice(lineBounds[escapedLineIndex], lineBounds[escapedLineIndex + 1]);
          findTextInLine(results, stripLineEscapeCodes(line), chunk.firstLine + escapedLineIndex,
            matcherFn);
          linesWithEscapesIndex++;
        }

        // linesWithEscapeIndex got updated, check if the current result from `text` is in an
        // escaped line.
        if (linesWithEscapesIndex < linesWithEscapes.length &&
          lineIndex === linesWithEscapes[linesWithEscapesIndex]) {
          // Skip results from escaped line
          match = matcherFn(text, match.pos + match.length);
          continue;
        }
      }
    }

    results.push({
      lineIndex: lineIndex + chunk.firstLine,
      lineStart: match.pos - lineBounds[lineIndex],
      lineEnd: (match.pos - lineBounds[lineIndex]) + match.length,
    });
    match = matcherFn(text, match.pos + match.length);
  }

  while (linesWithEscapesIndex < linesWithEscapes.length) {
    const escapedLineIndex = linesWithEscapes[linesWithEscapesIndex];
    const line = text.slice(lineBounds[escapedLineIndex], lineBounds[escapedLineIndex + 1]);
    findTextInLine(results, stripLineEscapeCodes(line), chunk.firstLine + escapedLineIndex,
      matcherFn);
    linesWithEscapesIndex++;
  }

  return results;
}

export function findTextInChunk(chunk: ParsedLogChunk,
                                searchString: string, options?: ChunkSearchOptions): ChunkSearchResults {
  const matcherFn = getMatcher(searchString, options);
  const results = findTextInChunkRaw(chunk, matcherFn);
  return {results, lineIndexToFirstChunkIndex: resultsListToLineIndexMap(results)};
}

// Returns null if no overlay is needed
export function overlaySearchResultsOnLine(chunkResults: ChunkSearchResults,
                                           lineIndex: number,
                                           lineLength: number,
                                           lineCssClasses: LineCssClasses[]|null,
                                           beginCssClasses: string,
                                           cssClasses: string,
                                           endCssClasses: string) {
  const firstChunkIndex = chunkResults.lineIndexToFirstChunkIndex.get(lineIndex);
  if (firstChunkIndex === undefined) {
    return null;
  }

  const beginCssClassesAll = combineCssClasses(cssClasses, beginCssClasses);
  const endCssClassesAll = combineCssClasses(cssClasses, endCssClasses);
  const beginEndCssClassesAll = combineCssClasses(beginCssClassesAll, endCssClasses);


  for (let i = firstChunkIndex; i < chunkResults.results.length; ++i) {
    const result = chunkResults.results[i];
    if (result.lineIndex !== lineIndex) {
      break;
    }
    const beginPos = result.lineStart;
    const endPos = result.lineEnd;

    const highlighLen = endPos - beginPos;

    if (highlighLen === 1) {
      lineCssClasses = addOverlayToCssClasses(lineLength, lineCssClasses,
        beginPos, endPos, beginEndCssClassesAll);
    } else if (highlighLen === 2) {
      lineCssClasses = addOverlayToCssClasses(lineLength, lineCssClasses,
        beginPos, beginPos + 1, beginCssClassesAll);
      lineCssClasses = addOverlayToCssClasses(lineLength, lineCssClasses,
        beginPos + 1, endPos, endCssClassesAll);
    } else {
      lineCssClasses = addOverlayToCssClasses(lineLength, lineCssClasses,
        beginPos, beginPos + 1, beginCssClassesAll);
      lineCssClasses = addOverlayToCssClasses(lineLength, lineCssClasses,
        beginPos + 1, endPos - 1, cssClasses);
      lineCssClasses = addOverlayToCssClasses(lineLength, lineCssClasses,
        endPos - 1, endPos, endCssClassesAll);
    }
  }
  return lineCssClasses;
}
