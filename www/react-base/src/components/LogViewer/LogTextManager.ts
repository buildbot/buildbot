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

import {ListOnItemsRenderedProps} from "react-window";
import {CancellablePromise} from "buildbot-data-js";
import {escapeClassesToHtml} from "../../util/AnsiEscapeCodes";
import {repositionPositionedArray} from "../../util/Array";
import {binarySearchGreater, binarySearchLessEqual} from "../../util/BinarySearch";
import {
  ChunkCssClasses, mergeChunks,
  parseCssClassesForChunk,
  ParsedLogChunk,
  parseLogChunk
} from "../../util/LogChunkParsing";
import {
  ChunkSearchOptions,
  ChunkSearchResults, findNextSearchResult, findPrevSearchResult, findTextInChunk,
  overlaySearchResultsOnLine
} from "../../util/LogChunkSearch";
import {
  alignCeil,
  alignFloor,
  areRangesOverlapping,
  expandRange,
  isRangeWithinAnother,
  limitRangeToSize
} from "../../util/Math";
import {LineCssClasses} from "../../util/LineCssClasses";

export type PendingRequest = {
  promise: CancellablePromise<any>;
  startIndex: number;
  endIndex: number;
}

export type LineRenderer = (index: number, lineType: string, style: React.CSSProperties,
                            lineContent: JSX.Element[]) => JSX.Element;

export type EmptyLineRenderer =
  (index: number, style: React.CSSProperties) => JSX.Element;

export class LogTextManager {
  renderedLinesStartIndex = 0;
  renderedLines: (JSX.Element|undefined)[] = [];
  // Valid only if searchString !== null
  renderedLinesForSearch: (JSX.Element|null|undefined)[] = [];

  dataGetter: (offset: number, limit: number) => CancellablePromise<any>;
  logType: string;

  // Controls the number of additional downloaded lines that are maintained outside the visible
  // range. If the number of additional lines becomes lower, a download is initiated.
  downloadInitiateOverscanRowCount: number;

  // Controls the number of additional lines that are downloaded outside the visible range if a
  // download is requested. This number is usually greater than downloadInitiateOverscanRowCount
  // so that if a download is requested it retrieves more lines than needed.
  downloadOverscanRowCount: number;

  // How many lines outside the visible range are cached in downloaded form.
  cachedDownloadOverscanRowCount: number;

  // How many lines outside the visible range are cached as rendered form.
  cacheRenderedOverscanRowCount: number;

  onStateChange: () => void;

  logNumLines = 0; // kept up to date

  pendingRequest: PendingRequest|null = null;

  chunks: ParsedLogChunk[] = [];
  // Represents cached chunk CSS class information for each chunk. The array must have the same size
  // as the `chunks` array at all times.
  chunkToCssClasses: (ChunkCssClasses|null)[] = [];

  // The maximum size of a chunk. This controls the size of the chunk as requested from the API and
  // the size of chunks selected for merging.
  maxChunkLinesCount = 1000;

  // Certain errors are unrecoverable and further logs won't be downloaded from the backend
  disableDownloadDueToError = false;

  // The start and end index of currently visible data. From this we compute all other different
  // line ranges:
  //  - download line range: line range for which line data should be fetched
  //  - cached rendered line range: line range for which already rendered lines are cached
  //  - cached download line range: line range for which already downloaded log data is kept
  currVisibleStartIndex = 0;
  currVisibleEndIndex = 0;

  prevVisibleStartIndex = 0;
  prevVisibleEndIndex = 0;

  // Whether search is active and whole log should be downloaded. Note that once search becomes
  // active, the page will keep whole log in memory.
  searchWasEnabled = false;

  // Current search string or null if no search is being performed at the moment
  searchString: string|null = null;
  searchOptions: ChunkSearchOptions = {caseInsensitive: false, useRegex: false}
  // Valid only if searchString !== null. Indices are the same as this.chunks
  chunkSearchResults: ChunkSearchResults[] = [];
  // Valid only if searchString !== null
  currentSearchResultIndex: number = -1;
  // Valid only if searchString !== null
  currentSearchResultChunkIndex: number = -1;
  // Valid only if searchString !== null
  currentSearchResultIndexInChunk: number = -1;
  // Valid only if searchString !== null
  totalSearchResultCount: number = -1;

  // Ensures that when a selection is active no rows are removed from the set of nodes rendered
  // by React. Otherwise removed nodes will break selection.
  isSelectionActive = false;
  selectionStartIndex = 0;
  selectionEndIndex = 0;

  lastRenderStartIndex = 0;
  lastRenderEndIndex = 0;

  constructor(dataGetter: (offset: number, limit: number) => CancellablePromise<any>,
              logType: string,
              downloadInitiateOverscanRowCount: number,
              downloadOverscanRowCount: number, cachedDownloadOverscanRowCount: number,
              cacheRenderedOverscanRowCount: number,
              maxChunkLinesCount: number,
              onStateChange: () => void) {
    this.dataGetter = dataGetter;
    this.logType = logType;
    this.downloadInitiateOverscanRowCount = downloadInitiateOverscanRowCount;
    this.downloadOverscanRowCount = downloadOverscanRowCount;
    this.cachedDownloadOverscanRowCount = cachedDownloadOverscanRowCount;
    this.cacheRenderedOverscanRowCount = cacheRenderedOverscanRowCount;
    this.maxChunkLinesCount = maxChunkLinesCount;
    this.onStateChange = onStateChange;
  }

  downloadInitiateLineRange(): [number, number] {
    if (this.searchWasEnabled) {
      return [0, this.logNumLines];
    }
    return expandRange(this.currVisibleStartIndex, this.currVisibleEndIndex, 0, this.logNumLines,
      this.downloadInitiateOverscanRowCount);
  }

  downloadLineRange(): [number, number] {
    if (this.searchWasEnabled) {
      return [0, this.logNumLines];
    }
    return expandRange(this.currVisibleStartIndex, this.currVisibleEndIndex, 0, this.logNumLines,
      this.downloadOverscanRowCount);
  }

  cachedDownloadLineRange(): [number, number] {
    return expandRange(this.currVisibleStartIndex, this.currVisibleEndIndex, 0, this.logNumLines,
      this.cachedDownloadOverscanRowCount);
  }

  cachedRenderedLineRange(): [number, number] {
    const [start, end] = expandRange(this.currVisibleStartIndex, this.currVisibleEndIndex,
      0, this.logNumLines, this.cacheRenderedOverscanRowCount);
    const cacheBoundStep = 128;
    return [alignFloor(start, cacheBoundStep), alignCeil(end, cacheBoundStep)];
  }

  downloadedLinesStartIndex() {
    if (this.chunks.length === 0) {
      return 0;
    }
    return this.chunks[0].firstLine;
  }

  downloadedLinesEndIndex() {
    if (this.chunks.length === 0) {
      return 0;
    }
    return this.chunks[this.chunks.length - 1].lastLine;
  }

  setIsSelectionActive(currIsSelectionActive: boolean) {
    if (currIsSelectionActive && !this.isSelectionActive) {
      this.selectionStartIndex = this.lastRenderStartIndex;
      this.selectionEndIndex = this.lastRenderEndIndex;
    }
    this.isSelectionActive = currIsSelectionActive;
  }

  onCellRangeRendered(startIndex: number, endIndex: number) {
    this.lastRenderStartIndex = startIndex;
    this.lastRenderEndIndex = endIndex;
    if (this.isSelectionActive) {
      if (startIndex < this.selectionStartIndex) {
        this.selectionStartIndex = startIndex;
      }
      if (endIndex > this.selectionEndIndex) {
        this.selectionEndIndex = endIndex;
      }
    }
  }

  updateCachedRenderedLines() {
    let [newStartIndex, newEndIndex] = this.cachedRenderedLineRange();
    const startIndex = this.renderedLinesStartIndex;
    const endIndex = startIndex + this.renderedLines.length;

    if (this.isSelectionActive) {
      // Don't drop lines if selection is active
      newStartIndex = Math.min(newStartIndex, startIndex);
      newEndIndex = Math.max(newEndIndex, endIndex);
    }

    if (newStartIndex === startIndex && newEndIndex === endIndex) {
      return;
    }

    const oldRenderedLinesStartIndex = this.renderedLinesStartIndex;
    [this.renderedLines, this.renderedLinesStartIndex] =
      repositionPositionedArray(this.renderedLines, oldRenderedLinesStartIndex,
        newStartIndex, newEndIndex);

    if (this.searchString !== null) {
      this.renderedLinesForSearch =
        repositionPositionedArray(this.renderedLinesForSearch, oldRenderedLinesStartIndex,
          newStartIndex, newEndIndex)[0];
    }
  }

  cleanupDownloadedLines() {
    if (this.chunks.length === 0 || this.isSelectionActive) {
      return;
    }
    const [currStart, currEnd] = this.cachedDownloadLineRange();
    if (this.chunks[0].firstLine >= currEnd ||
      this.chunks[this.chunks.length - 1].lastLine <= currStart) {
      // Does not fall within the range at all
      this.chunks = [];
      this.chunkToCssClasses = [];
      this.chunkSearchResults = [];
      return;
    }

    let leaveStart = 0;
    let leaveEnd = this.chunks.length;

    while (this.chunks[leaveStart].lastLine <= currStart) {
      leaveStart++;
    }
    while (this.chunks[leaveEnd - 1].firstLine >= currEnd) {
      leaveEnd--;
    }

    if (leaveStart !== 0 || leaveEnd !== this.chunks.length) {
      this.chunks = this.chunks.slice(leaveStart, leaveEnd - leaveStart);
      this.chunkToCssClasses = this.chunkToCssClasses.slice(leaveStart, leaveEnd - leaveStart);
      if (this.searchString !== null) {
        this.chunkSearchResults = this.chunkSearchResults.slice(leaveStart, leaveEnd - leaveStart);
      }
    }
  }

  addChunk(chunk: ParsedLogChunk) {
    if (this.chunks.length === 0) {
      this.chunks.push(chunk);
      this.chunkToCssClasses.push(null);
      this.maybeInsertChunkSearchResults(0);
      return;
    }

    const insertIndex = binarySearchGreater(this.chunks, chunk.firstLine,
      (ch, line) => ch.firstLine - line);

    // The inserted chunk must always be contiguous with already existing chunks. If this is not the
    // case, then the API returned wrong data.
    if (insertIndex !== 0) {
      const prevChunk = this.chunks[insertIndex - 1];
      if (prevChunk.lastLine !== chunk.firstLine) {
        this.disableDownloadDueToError = true;
        throw Error(`Received incontiguous chunk range ${chunk.firstLine}..${chunk.lastLine} vs ` +
          `${prevChunk.firstLine}..${prevChunk.lastLine}`);
      }
    }

    if (insertIndex !== this.chunks.length) {
      const nextChunk = this.chunks[insertIndex];
      if (nextChunk.firstLine !== chunk.lastLine) {
        this.disableDownloadDueToError = true;
        throw Error(`Received incontiguous chunk range ${chunk.firstLine}..${chunk.lastLine} vs ` +
          `${nextChunk.firstLine}..${nextChunk.lastLine}`);
      }
    }

    if (this.maybeMergeIntoChunk(insertIndex - 1, chunk, false)) {
      return;
    }
    if (this.maybeMergeIntoChunk(insertIndex, chunk, true)) {
      return;
    }
    this.chunks.splice(insertIndex, 0, chunk);
    this.chunkToCssClasses.splice(insertIndex, 0, null);
    this.maybeInsertChunkSearchResults(insertIndex);
  }

  private maybeMergeIntoChunk(mergeIndex: number, chunk: ParsedLogChunk, prepend: boolean) {
    if (mergeIndex < 0 || mergeIndex >= this.chunks.length) {
      return false;
    }
    const mergeChunkLength = this.chunks[mergeIndex].lastLine - this.chunks[mergeIndex].firstLine;
    const chunkLength = chunk.lastLine - chunk.firstLine;

    if (mergeChunkLength + chunkLength < this.maxChunkLinesCount) {
      return false;
    }

    if (prepend) {
      this.chunks[mergeIndex] = mergeChunks(chunk, this.chunks[mergeIndex]);
    } else {
      this.chunks[mergeIndex] = mergeChunks(this.chunks[mergeIndex], chunk);
    }
    if (this.chunkToCssClasses[mergeIndex] !== null) {
      // There was a need for CSS class information, and it wasn't cleared yet. This means that
      // this information is useful and shouldn't be dropped yet. Additionally, the CSS class
      // information for the prepended/appended chunk is likely to be needed. Thus, it doesn't
      // hurt to compute CSS class information for whole chunk.
      const chunkCssClasses = parseCssClassesForChunk(chunk, chunk.firstLine, chunk.lastLine);
      this.chunkToCssClasses[mergeIndex] = {
        ...chunkCssClasses,
        ...this.chunkToCssClasses[mergeIndex]
      };
    }
    this.maybeMergeChunkSearchResults(mergeIndex, prepend);
    return true;
  }

  clearCache() {
    this.renderedLines = [];
    this.renderedLines[this.renderedLines.length] = undefined; // preallocate
    this.renderedLinesForSearch = [];
    this.renderedLinesForSearch[this.renderedLines.length] = undefined; // preallocate
  }

  getRenderedLineContent(index: number, style: React.CSSProperties,
                         renderer: LineRenderer, emptyRenderer: EmptyLineRenderer) {
    if (this.searchString !== null) {
      const renderedLineForSearch = this.renderedLinesForSearch[index - this.renderedLinesStartIndex];
      if (renderedLineForSearch === null) {
        const renderedLine = this.renderedLines[index - this.renderedLinesStartIndex];
        if (renderedLine !== undefined) {
          return renderedLine;
        }
      } else if (renderedLineForSearch !== undefined &&
          index !== this.getCurrentSearchResultLine()) {
        return renderedLineForSearch;
      }
    } else {
      const renderedLine = this.renderedLines[index - this.renderedLinesStartIndex];
      if (renderedLine !== undefined) {
        return renderedLine;
      }
    }

    const downloadedStartIndex = this.downloadedLinesStartIndex();
    const downloadedEndIndex = this.downloadedLinesEndIndex();

    if (index < downloadedStartIndex || index >= downloadedEndIndex) {
      return emptyRenderer(index, style);
    }

    // Chunks form a contiguous range so at this point line is guaranteed to point to a valid chunk
    const chunkIndex = binarySearchLessEqual(this.chunks, index,
      (ch, index) => ch.firstLine - index);
    const chunk = this.chunks[chunkIndex];
    const lineIndexInChunk = index - chunk.firstLine;
    const lineType = chunk.lineTypes[lineIndexInChunk];
    const lineStartInChunk = chunk.textLineBounds[lineIndexInChunk];
    const lineEndInChunk = chunk.textLineBounds[lineIndexInChunk + 1] - 1; // exclude trailing newline
    const lineCssClassesWithText = this.getCssClassesForChunk(chunkIndex)[lineIndexInChunk];
    const lineContent = escapeClassesToHtml(chunk.text, lineStartInChunk, lineEndInChunk,
      lineCssClassesWithText);

    const renderedContent = renderer(index, lineType, style, lineContent);
    if (index >= this.renderedLinesStartIndex) {
      this.renderedLines[index - this.renderedLinesStartIndex] = renderedContent;
    }

    if (this.searchString !== null) {
      const chunkSearchResults = this.chunkSearchResults[chunkIndex];
      const lineLength = lineEndInChunk - lineStartInChunk;
      const lineCssClassesForSearch =
        overlaySearchResultsOnLine(chunkSearchResults, index, lineLength,
          lineCssClassesWithText === undefined ? null : lineCssClassesWithText[1],
          "bb-logviewer-result-begin", "bb-logviewer-result", "bb-logviewer-result-end");

      if (lineCssClassesForSearch === null) {
        if (index >= this.renderedLinesStartIndex) {
          this.renderedLinesForSearch[index - this.renderedLinesStartIndex] = null;
        }
        return renderedContent;
      }

      const lineContentForSearch = escapeClassesToHtml(chunk.text, lineStartInChunk, lineEndInChunk,
        [lineCssClassesWithText === undefined ? null : lineCssClassesWithText[0],
          lineCssClassesForSearch]);
      const renderedContentForSearch = renderer(index, lineType, style, lineContentForSearch);
      if (index >= this.renderedLinesStartIndex) {
        this.renderedLinesForSearch[index - this.renderedLinesStartIndex] = renderedContentForSearch;
      }

      if (index === this.getCurrentSearchResultLine()) {
        // render uncached contents with the current line highlighted
        const fakeHighlightedChunkResult: ChunkSearchResults = {
          results: [this.getCurrentSearchChunkResult()!],
          lineIndexToFirstChunkIndex: new Map<number, number>([[index, 0]]),
        }
        const lineCssClassesForSearchHighlight =
            overlaySearchResultsOnLine(fakeHighlightedChunkResult, index,
                lineLength, lineCssClassesForSearch,
                "", "bb-logviewer-result-current", "");

        const lineContentForSearchHighlight = escapeClassesToHtml(
            chunk.text, lineStartInChunk, lineEndInChunk,
            [lineCssClassesWithText === undefined ? null : lineCssClassesWithText[0],
              lineCssClassesForSearchHighlight]);
        return renderer(index, lineType, style, lineContentForSearchHighlight);
      }
      return renderedContentForSearch;
    }
    return renderedContent;
  }

  setLogNumLines(numLines: number) {
    if (this.logNumLines === numLines) {
      return;
    }
    this.logNumLines = numLines;
    this.maybeUpdatePendingRequest(0, 0);
  }

  setSearchCaseSensitivity(sensitive: boolean) {
    const caseInsensitive = !sensitive;
    if (this.searchOptions.caseInsensitive === caseInsensitive) {
      return;
    }
    this.searchOptions.caseInsensitive = caseInsensitive;

    this.onSearchInputChanged();
  }

  setUseRegex(value: boolean) {
    const useRegex = value;
    if (this.searchOptions.useRegex === useRegex) {
      return;
    }
    this.searchOptions.useRegex = useRegex;

    this.onSearchInputChanged();
  }

  setSearchString(searchString: string|null) {
    if (searchString === this.searchString) {
      return;
    }
    this.searchString = searchString;

    this.onSearchInputChanged();
  }

  private onSearchInputChanged() {
    this.currentSearchResultChunkIndex = -1;
    this.currentSearchResultIndexInChunk = -1;
    this.currentSearchResultIndex = -1;
    this.totalSearchResultCount = 0;

    if (this.searchString === null) {
      this.chunkSearchResults = [];
      this.renderedLinesForSearch = [];
      this.onStateChange();
      return;
    }

    if (!this.searchWasEnabled) {
      this.searchWasEnabled = true;
      this.maybeUpdatePendingRequest(0, 0);
    }
    this.chunkSearchResults = new Array(this.chunks.length);
    this.renderedLinesForSearch = [];
    this.totalSearchResultCount = 0;
    this.currentSearchResultIndex = 0;

    for (let i = 0; i < this.chunks.length; ++i) {
      const newResult = findTextInChunk(this.chunks[i], this.searchString, this.searchOptions);
      this.chunkSearchResults[i] = newResult;
      this.totalSearchResultCount += newResult.results.length;
      if (this.currentSearchResultChunkIndex < 0 && newResult.results.length > 0) {
        this.currentSearchResultChunkIndex = i;
        this.currentSearchResultIndexInChunk = 0;
      }
    }
    this.onStateChange();
  }

  getCurrentSearchResultLine() {
    if (this.currentSearchResultChunkIndex < 0) {
      return -1;
    }
    const chunkResults = this.chunkSearchResults[this.currentSearchResultChunkIndex].results;
    return chunkResults[this.currentSearchResultIndexInChunk].lineIndex;
  }

  getCurrentSearchChunkResult() {
    if (this.currentSearchResultChunkIndex < 0) {
      return null;
    }
    const chunkResults = this.chunkSearchResults[this.currentSearchResultChunkIndex].results;
    return chunkResults[this.currentSearchResultIndexInChunk];
  }

  setNextSearchResult() {
    if (this.currentSearchResultChunkIndex < 0 || this.totalSearchResultCount === 0) {
      return;
    }
    this.currentSearchResultIndex += 1;
    if (this.currentSearchResultIndex === this.totalSearchResultCount) {
      this.currentSearchResultIndex = 0;
    }
    [this.currentSearchResultChunkIndex, this.currentSearchResultIndexInChunk] =
      findNextSearchResult(this.chunkSearchResults, this.currentSearchResultChunkIndex,
        this.currentSearchResultIndexInChunk);
    this.onStateChange();
  }

  setPrevSearchResult() {
    if (this.currentSearchResultChunkIndex < 0 || this.totalSearchResultCount === 0) {
      return;
    }
    if (this.currentSearchResultIndex === 0) {
      // wrap around
      this.currentSearchResultIndex = this.totalSearchResultCount;
    }
    this.currentSearchResultIndex--;
    [this.currentSearchResultChunkIndex, this.currentSearchResultIndexInChunk] =
      findPrevSearchResult(this.chunkSearchResults, this.currentSearchResultChunkIndex,
        this.currentSearchResultIndexInChunk);
    this.onStateChange();
  }

  maybeInsertChunkSearchResults(insertIndex: number) {
    if (this.searchString === null) {
      return;
    }
    const newResult = findTextInChunk(this.chunks[insertIndex], this.searchString!, this.searchOptions);
    this.chunkSearchResults.splice(insertIndex, 0, newResult);
    this.totalSearchResultCount += newResult.results.length;

    if (this.currentSearchResultChunkIndex < 0) {
      if (newResult.results.length > 0) {
        this.currentSearchResultChunkIndex = insertIndex;
        this.currentSearchResultIndexInChunk = 0;
        this.currentSearchResultIndex = 0;
      }
    } else if (insertIndex <= this.currentSearchResultChunkIndex) {
      this.currentSearchResultChunkIndex++;
      this.currentSearchResultIndex += newResult.results.length;
    }
  }

  maybeMergeChunkSearchResults(mergeIndex: number, prepend: boolean) {
    if (this.searchString === null) {
      return;
    }
    const prevResult = this.chunkSearchResults[mergeIndex];
    const newResult = findTextInChunk(this.chunks[mergeIndex], this.searchString!, this.searchOptions);
    const additionalResultsCount = newResult.results.length - prevResult!.results.length;

    this.chunkSearchResults[mergeIndex] = newResult;
    this.totalSearchResultCount += additionalResultsCount;

    if (this.currentSearchResultChunkIndex < 0) {
      if (newResult.results.length > 0) {
        this.currentSearchResultChunkIndex = mergeIndex;
        this.currentSearchResultIndexInChunk = 0;
        this.currentSearchResultIndex = 0;
      }
    } else if (mergeIndex === this.currentSearchResultChunkIndex) {
      if (prepend) {
        this.currentSearchResultIndexInChunk += additionalResultsCount;
        this.currentSearchResultIndex += additionalResultsCount;
      }
    }
  }

  getCssClassesForChunk(chunkIndex: number) {
    let cssClasses = this.chunkToCssClasses[chunkIndex];
    if (cssClasses === null) {
      const chunk = this.chunks[chunkIndex];
      cssClasses = parseCssClassesForChunk(chunk, chunk.firstLine, chunk.lastLine);
      this.chunkToCssClasses[chunkIndex] = cssClasses;
    }
    return cssClasses;
  }

  static shouldKeepPendingRequest(downloadedStart: number, downloadedEnd: number,
                                  downloadedPinned: boolean,
                                  requestedStart: number, requestedEnd: number,
                                  visibleStart: number, visibleEnd: number) {
    if (downloadedPinned ||
        isRangeWithinAnother(visibleStart, visibleEnd, downloadedStart, downloadedEnd)) {
      return true;
    }
    return areRangesOverlapping(visibleStart, visibleEnd, requestedStart, requestedEnd);
  }

  static selectChunkDownloadRange(downloadStart: number, downloadEnd: number,
                                  downloadedStart: number, downloadedEnd: number,
                                  visibleStart: number, visibleEnd: number,
                                  cachedDownloadOverscanRowCount: number,
                                  maxSizeLimit: number): [number, number] {
    const visibleCenter = Math.floor((visibleStart + visibleEnd) / 2);
    if (downloadedStart >= downloadedEnd) {
      return limitRangeToSize(downloadStart, downloadEnd, maxSizeLimit, visibleCenter);
    }

    // During caching calculations existing downloaded data is not discarded until it's
    // too far away from visible data by cachedDownloadOverscanRowCount. To avoid gaps in
    // downloaded data, downloaded range needs to be expanded for the case when existing
    // data is thrown away.
    const expandedDownloadedStart = downloadedStart - cachedDownloadOverscanRowCount;
    const expandedDownloadedEnd = downloadedEnd + cachedDownloadOverscanRowCount;

    if (!areRangesOverlapping(downloadStart, downloadEnd,
        expandedDownloadedStart, expandedDownloadedEnd)) {
      // In case of pinned downloaded range, the download range must extend the downloaded range,
      // so there's guarantee that there are no gaps.
      return limitRangeToSize(downloadStart, downloadEnd, maxSizeLimit, visibleCenter);
    }

    if (isRangeWithinAnother(downloadStart, downloadEnd, downloadedStart, downloadedEnd)) {
      return [0, 0];
    }

    if (!isRangeWithinAnother(downloadedStart, downloadedEnd, downloadStart, downloadEnd)) {
      if (downloadStart < downloadedStart) {
        downloadEnd = downloadedStart;
        return limitRangeToSize(downloadStart, downloadEnd, maxSizeLimit, downloadedStart);
      }
      // downloadEnd > downloadedEnd
      downloadStart = downloadedEnd;
      return limitRangeToSize(downloadStart, downloadEnd, maxSizeLimit, downloadedEnd);
    }

    // Downloaded range is within range to download, with the range to download extending the
    // downloaded range from both sides. The parts that overlap with currently visible lines
    // are selected for downloading first. If both parts overlap, then the last part is downloaded.
    const firstPartStart = downloadStart;
    const firstPartEnd = downloadedStart;
    const lastPartStart = downloadedEnd;
    const lastPartEnd = downloadEnd;

    const firstPartWithVisible =
      areRangesOverlapping(firstPartStart, firstPartEnd, visibleStart, visibleEnd);
    const lastPartWithVisible =
      areRangesOverlapping(lastPartStart, lastPartEnd, visibleStart, visibleEnd);

    if ((firstPartWithVisible && lastPartWithVisible) || !firstPartWithVisible) {
      return limitRangeToSize(lastPartStart, lastPartEnd, maxSizeLimit, lastPartStart);
    }
    return limitRangeToSize(firstPartStart, firstPartEnd, maxSizeLimit, firstPartEnd);
  }

  requestRows(info: ListOnItemsRenderedProps) {
    this.prevVisibleStartIndex = this.currVisibleStartIndex;
    this.prevVisibleEndIndex = this.currVisibleEndIndex;
    this.currVisibleStartIndex = info.visibleStartIndex;
    this.currVisibleEndIndex = info.visibleStopIndex;
    this.updateCachedRenderedLines();
    this.maybeUpdatePendingRequest(info.overscanStartIndex, info.overscanStopIndex);
  }

  maybeUpdatePendingRequest(overscanStartIndex: number, overscanEndIndex: number) {
    if (this.disableDownloadDueToError) {
      return;
    }

    const downloadedStartIndex = this.downloadedLinesStartIndex();
    const downloadedEndIndex = this.downloadedLinesEndIndex();

    if (!this.searchWasEnabled) {
      if (overscanStartIndex >= overscanEndIndex) {
        return;
      }

      if (isRangeWithinAnother(overscanStartIndex, overscanEndIndex,
        downloadedStartIndex, downloadedEndIndex)) {
        return;
      }
    }

    const [initiateStartIndex, initiateEndIndex] = this.downloadInitiateLineRange();
    if (isRangeWithinAnother(initiateStartIndex, initiateEndIndex,
        downloadedStartIndex, downloadedEndIndex)) {
      return;
    }

    if (this.pendingRequest) {
      if (LogTextManager.shouldKeepPendingRequest(
            downloadedStartIndex, downloadedEndIndex, this.searchWasEnabled,
            this.pendingRequest.startIndex, this.pendingRequest.endIndex,
            this.currVisibleStartIndex, this.currVisibleEndIndex)) {
        return;
      }
      this.pendingRequest.promise.cancel();
      this.pendingRequest = null;
    }

    const [downloadStartIndex, downloadEndIndex] = this.downloadLineRange();
    const [chunkDownloadStartIndex, chunkDownloadEndIndex] =
      LogTextManager.selectChunkDownloadRange(downloadStartIndex, downloadEndIndex,
        downloadedStartIndex, downloadedEndIndex,
        this.currVisibleStartIndex, this.currVisibleEndIndex, this.cachedDownloadOverscanRowCount,
        this.maxChunkLinesCount);

    if (chunkDownloadStartIndex >= chunkDownloadEndIndex) {
      return;
    }

    this.pendingRequest = {
      promise: this.dataGetter(chunkDownloadStartIndex,
          chunkDownloadEndIndex - chunkDownloadStartIndex),
      startIndex: chunkDownloadStartIndex,
      endIndex: chunkDownloadEndIndex,
    };
    this.pendingRequest.promise.then(response => {
      const content = response.logchunks[0].content as string;
      const chunk = parseLogChunk(chunkDownloadStartIndex, content, this.logType);
      this.cleanupDownloadedLines();
      this.addChunk(chunk);
      this.onStateChange();
      this.pendingRequest = null;
      this.maybeUpdatePendingRequest(this.currVisibleStartIndex, this.currVisibleEndIndex);
    }).catch((e: Error) => {
      if (e.name === "CanceledError") {
        return;
      }
      throw e;
    })
  }
}
