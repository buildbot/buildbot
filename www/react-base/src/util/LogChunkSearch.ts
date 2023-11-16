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

export type ChunkSearchResult = {
  // Global line index
  lineIndex: number;
  // The location of the found search string occurrence
  lineStart: number;
};

export type ChunkSearchResults = {
  results: ChunkSearchResult[];
  lineIndexToFirstChunkIndex: Map<number, number>;
};

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
                        searchString: string) {
  let pos = text.indexOf(searchString, 0);
  while (pos >= 0) {
    results.push({
      lineIndex: lineIndex,
      lineStart: pos,
    });
    pos = text.indexOf(searchString, pos + searchString.length);
  }
}

export function findTextInChunkRaw(chunk: ParsedLogChunk,
                                   searchString: string): ChunkSearchResult[] {
  const searchNoPerLineEscapes =
    chunk.linesWithEscapes === null || chunk.linesWithEscapes.length === 0;

  if (searchNoPerLineEscapes) {
    const text = chunk.textNoEscapes !== null ? chunk.textNoEscapes : chunk.text;
    const lineBounds = chunk.textNoEscapesLineBounds !== null
      ? chunk.textNoEscapesLineBounds : chunk.textLineBounds;

    const results: ChunkSearchResult[] = [];
    let pos = text.indexOf(searchString, 0);
    let lineIndex = 0;
    while (pos >= 0) {
      lineIndex = maybeAdvanceLineIndexToBound(lineIndex, pos, lineBounds);
      results.push({
        lineIndex: lineIndex + chunk.firstLine,
        lineStart: pos - lineBounds[lineIndex]
      });
      pos = text.indexOf(searchString, pos + searchString.length);
    }
    return results;
  }

  // Hybrid search by searching text without escape sequences and handling lines with escape
  // sequences as a special case.

  const text = chunk.text;
  const lineBounds = chunk.textLineBounds;
  const linesWithEscapes = chunk.linesWithEscapes!;

  const results: ChunkSearchResult[] = [];
  let pos = text.indexOf(searchString, 0);
  let lineIndex = 0;
  let linesWithEscapesIndex = 0;

  while (pos >= 0) {
    lineIndex = maybeAdvanceLineIndexToBound(lineIndex, pos, lineBounds);

    if (linesWithEscapesIndex < linesWithEscapes.length) {
      if (lineIndex === linesWithEscapes[linesWithEscapesIndex]) {
        // Skip results from escaped line
        pos = text.indexOf(searchString, pos + searchString.length);
        continue;
      }
      if (lineIndex > linesWithEscapes[linesWithEscapesIndex]) {
        // Add results from any skipped escaped lines.
        while (linesWithEscapesIndex < linesWithEscapes.length &&
            lineIndex > linesWithEscapes[linesWithEscapesIndex]) {
          const escapedLineIndex = linesWithEscapes[linesWithEscapesIndex];
          const line = text.slice(lineBounds[escapedLineIndex], lineBounds[escapedLineIndex + 1]);
          findTextInLine(results, stripLineEscapeCodes(line), chunk.firstLine + escapedLineIndex,
            searchString);
          linesWithEscapesIndex++;
        }

        // linesWithEscapeIndex got updated, check if the current result from `text` is in an
        // escaped line.
        if (linesWithEscapesIndex < linesWithEscapes.length &&
          lineIndex === linesWithEscapes[linesWithEscapesIndex]) {
          // Skip results from escaped line
          pos = text.indexOf(searchString, pos + searchString.length);
          continue;
        }
      }
    }

    results.push({
      lineIndex: lineIndex + chunk.firstLine,
      lineStart: pos - lineBounds[lineIndex]
    });
    pos = text.indexOf(searchString, pos + searchString.length);
  }

  while (linesWithEscapesIndex < linesWithEscapes.length) {
    const escapedLineIndex = linesWithEscapes[linesWithEscapesIndex];
    const line = text.slice(lineBounds[escapedLineIndex], lineBounds[escapedLineIndex + 1]);
    findTextInLine(results, stripLineEscapeCodes(line), chunk.firstLine + escapedLineIndex,
      searchString);
    linesWithEscapesIndex++;
  }

  return results;
}

export function findTextInChunk(chunk: ParsedLogChunk,
                                searchString: string): ChunkSearchResults {
  const results = findTextInChunkRaw(chunk, searchString);
  return {results, lineIndexToFirstChunkIndex: resultsListToLineIndexMap(results)};
}

// Returns null if no overlay is needed
export function overlaySearchResultsOnLine(searchString: string,
                                           chunkResults: ChunkSearchResults,
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
    const endPos = beginPos + searchString.length;

    if (searchString.length === 1) {
      lineCssClasses = addOverlayToCssClasses(lineLength, lineCssClasses,
        beginPos, endPos, beginEndCssClassesAll);
    } else if (searchString.length === 2) {
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
