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

import {RenderedRows} from "react-virtualized/dist/es/List";
import {IDataAccessor} from "../../data/DataAccessor";
import {escapeClassesToHtml} from "../../util/AnsiEscapeCodes";
import {binarySearchGreater, binarySearchLessEqual} from "../../util/BinarySearch";
import {CancellablePromise} from "../../util/CancellablePromise";
import {
  ChunkCssClasses, mergeChunks,
  parseCssClassesForChunk,
  ParsedLogChunk,
  parseLogChunk
} from "../../util/LogChunkParsing";
import {
  areRangesOverlapping,
  expandRange,
  isRangeWithinAnother,
  limitRangeToSize
} from "../../util/Math";

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
  lines: {[num: number]: JSX.Element} = {};

  accessor: IDataAccessor;
  logid: number;
  logType: string;
  downloadInitiateOverscanRowCount: number;
  downloadOverscanRowCount: number;
  cachedDownloadOverscanRowCount: number;
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

  // Ensures that when a selection is active no rows are removed from the set of nodes rendered
  // by React. Otherwise removed nodes will break selection.
  isSelectionActive = false;
  selectionStartIndex = 0;
  selectionEndIndex = 0;

  lastRenderStartIndex = 0;
  lastRenderEndIndex = 0;

  constructor(accessor: IDataAccessor, logid: number, logType: string,
              downloadInitiateOverscanRowCount: number,
              downloadOverscanRowCount: number, cachedDownloadOverscanRowCount: number,
              cacheRenderedOverscanRowCount: number,
              maxChunkLinesCount: number,
              onStateChange: () => void) {
    this.accessor = accessor;
    this.logid = logid;
    this.logType = logType;
    this.downloadInitiateOverscanRowCount = downloadInitiateOverscanRowCount;
    this.downloadOverscanRowCount = downloadOverscanRowCount;
    this.cachedDownloadOverscanRowCount = cachedDownloadOverscanRowCount;
    this.cacheRenderedOverscanRowCount = cacheRenderedOverscanRowCount;
    this.maxChunkLinesCount = maxChunkLinesCount;
    this.onStateChange = onStateChange;
  }

  downloadInitiateLineRange(): [number, number] {
    return expandRange(this.currVisibleStartIndex, this.currVisibleEndIndex, 0, this.logNumLines,
      this.downloadInitiateOverscanRowCount);
  }

  downloadLineRange(): [number, number] {
    return expandRange(this.currVisibleStartIndex, this.currVisibleEndIndex, 0, this.logNumLines,
      this.downloadOverscanRowCount);
  }

  cachedDownloadLineRange(): [number, number] {
    return expandRange(this.currVisibleStartIndex, this.currVisibleEndIndex, 0, this.logNumLines,
      this.cachedDownloadOverscanRowCount);
  }

  cachedRenderedLineRange(): [number, number] {
    return expandRange(this.currVisibleStartIndex, this.currVisibleEndIndex, 0, this.logNumLines,
      this.cacheRenderedOverscanRowCount);
  }

  prevCachedRenderedLineRange(): [number, number] {
    return expandRange(this.prevVisibleStartIndex, this.prevVisibleEndIndex, 0, this.logNumLines,
      this.cacheRenderedOverscanRowCount);
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

  cleanupCachedRenderedLines() {
    if (this.isSelectionActive) {
      return;
    }

    const [currStart, currEnd] = this.cachedRenderedLineRange();
    const [prevStart, prevEnd] = this.prevCachedRenderedLineRange();

    if (prevStart === prevEnd) {
      return;
    }

    if (currStart >= prevEnd) {
      this.lines = {};
      return;
    }

    if (currEnd <= currStart) {
      this.lines = {};
      return;
    }

    for (let i = prevStart; i < currStart; ++i) {
      delete this.lines[i];
    }

    for (let i = currEnd; i < prevEnd; ++i) {
      delete this.lines[i];
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
    }
  }

  addChunk(chunk: ParsedLogChunk) {
    if (this.chunks.length === 0) {
      this.chunks.push(chunk);
      this.chunkToCssClasses.push(null);
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
    return true;
  }

  getRenderedLineContent(index: number, style: React.CSSProperties,
                         renderer: LineRenderer, emptyRenderer: EmptyLineRenderer) {
    const renderedLine = this.lines[index];
    if (renderedLine !== undefined) {
      return renderedLine;
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
    const lineCssClasses = this.getCssClassesForChunk(chunkIndex)[lineIndexInChunk];
    const lineStartInChunk = chunk.textLineBounds[lineIndexInChunk];
    const lineEndInChunk = chunk.textLineBounds[lineIndexInChunk + 1] - 1; // exclude trailing newline
    const lineContent = escapeClassesToHtml(chunk.text, lineStartInChunk, lineEndInChunk,
      lineCssClasses);

    const renderedContent = renderer(index, lineType, style, lineContent);
    this.lines[index] = renderedContent;
    return renderedContent;
  }

  setLogNumLines(numLines: number) {
    this.logNumLines = numLines;
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
                                  requestedStart: number, requestedEnd: number,
                                  visibleStart: number, visibleEnd: number) {
    if (isRangeWithinAnother(visibleStart, visibleEnd, downloadedStart, downloadedEnd)) {
      return true;
    }
    return areRangesOverlapping(visibleStart, visibleEnd, requestedStart, requestedEnd);
  }

  static selectChunkDownloadRange(downloadStart: number, downloadEnd: number,
                                  downloadedStart: number, downloadedEnd: number,
                                  visibleStart: number, visibleEnd: number,
                                  maxSizeLimit: number): [number, number] {
    const visibleCenter = Math.floor((visibleStart + visibleEnd) / 2);
    if (downloadedStart >= downloadedEnd) {
      return limitRangeToSize(downloadStart, downloadEnd, maxSizeLimit, visibleCenter);
    }

    if (!areRangesOverlapping(downloadStart, downloadEnd, downloadedStart, downloadedEnd)) {
      // In case of pinned downloaded range, the download range must extend the downloaded range
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

  requestRows(info: RenderedRows) {
    this.prevVisibleStartIndex = this.currVisibleStartIndex;
    this.prevVisibleEndIndex = this.currVisibleEndIndex;
    this.currVisibleStartIndex = info.startIndex;
    this.currVisibleEndIndex = info.stopIndex;
    this.cleanupCachedRenderedLines();

    if (this.disableDownloadDueToError) {
      return;
    }

    const downloadedStartIndex = this.downloadedLinesStartIndex();
    const downloadedEndIndex = this.downloadedLinesEndIndex();

    if (isRangeWithinAnother(info.overscanStartIndex, info.overscanStopIndex,
        downloadedStartIndex, downloadedEndIndex)) {
      return;
    }

    const [initiateStartIndex, initiateEndIndex] = this.downloadInitiateLineRange();
    if (isRangeWithinAnother(initiateStartIndex, initiateEndIndex,
        downloadedStartIndex, downloadedEndIndex)) {
      return;
    }

    if (this.pendingRequest) {
      if (LogTextManager.shouldKeepPendingRequest(
            downloadedStartIndex, downloadedEndIndex,
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
        this.currVisibleStartIndex, this.currVisibleEndIndex, this.maxChunkLinesCount);

    if (chunkDownloadStartIndex >= chunkDownloadEndIndex) {
      return;
    }

    this.pendingRequest = {
      promise: this.accessor.getRaw(`logs/${this.logid}/contents`, {
        offset: chunkDownloadStartIndex,
        limit: chunkDownloadEndIndex - chunkDownloadStartIndex
      }),
      startIndex: chunkDownloadStartIndex,
      endIndex: chunkDownloadEndIndex,
    };
    this.pendingRequest.promise.then(response => {
      const content = response.logchunks[0].content as string;
      const chunk = parseLogChunk(chunkDownloadStartIndex, content, this.logType);
      this.cleanupDownloadedLines();
      this.addChunk(chunk);
      this.onStateChange();
    }).catch((e: Error) => {
      if (e.name === "CanceledError") {
        return;
      }
      throw e;
    })
  }
}
