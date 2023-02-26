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
import {binarySearchGreater} from "../../util/BinarySearch";
import {CancellablePromise} from "../../util/CancellablePromise";
import {
  ChunkCssClasses,
  parseCssClassesForChunk,
  ParsedLogChunk,
  parseLogChunk
} from "../../util/LogChunkParsing";

export type RenderedLogLine = {
  content: JSX.Element | JSX.Element[];
  number: number;
}

export type PendingRequest = {
  promise: CancellablePromise<any>;
  startIndex: number;
  endIndex: number;
}

export class LogTextManager {
  lines: {[num: number]: RenderedLogLine} = {};

  accessor: IDataAccessor;
  logid: number;
  logType: string;
  fetchOverscanRowCount: number;
  destroyOverscanRowCount: number;
  onStateChange: () => void;

  logNumLines = 0; // kept up to date

  pendingRequest: PendingRequest|null = null;

  chunks: ParsedLogChunk[] = [];
  chunkToCssClasses: {[firstLine: string]: ChunkCssClasses} = {};

  // The start and end index of stored data
  startIndex = 0;
  endIndex = 0;

  // Ensures that when a selection is active no rows are removed from the set of nodes rendered
  // by React. Otherwise removed nodes will break selection.
  isSelectionActive = false;
  selectionStartIndex = 0;
  selectionEndIndex = 0;

  lastRenderStartIndex = 0;
  lastRenderEndIndex = 0;

  constructor(accessor: IDataAccessor, logid: number, logType: string,
              fetchOverscanRowCount: number, destroyOverscanRowCount: number,
              onStateChange: () => void) {
    this.accessor = accessor;
    this.logid = logid;
    this.logType = logType;
    this.fetchOverscanRowCount = fetchOverscanRowCount;
    this.destroyOverscanRowCount = destroyOverscanRowCount;
    this.onStateChange = onStateChange;
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

  cleanupLines(targetStartIndex: number, targetEndIndex: number) {
    if (targetStartIndex > this.endIndex) {
      this.startIndex = targetStartIndex;
      this.endIndex = targetStartIndex;
      this.lines = {};
      return;
    }

    if (targetEndIndex < this.startIndex) {
      this.startIndex = targetEndIndex;
      this.endIndex = targetEndIndex;
      this.lines = {};
      return;
    }

    if (this.startIndex < targetStartIndex) {
      for (let i = this.startIndex; i < targetStartIndex; ++i) {
        delete this.lines[i];
      }
      this.startIndex = targetStartIndex;
    }
    if (targetEndIndex < this.endIndex) {
      for (let i = targetEndIndex; i < this.endIndex; ++i) {
        delete this.lines[i];
      }
      this.endIndex = targetEndIndex;
    }
  }

  addDownloadedRange(startIndex: number, endIndex: number,
                     destroyOverscanRowCount: number) {
    // There are 3 areas where each of startIndex and endIndex can fall to:
    //  a) X < this.startIndex
    //  b) X >= this.startIndex && X <= this.endIndex
    //  c) X > this.endIndex
    // Given that there are both startIndex and endIndex, there are total of 9 combinations.
    // Because startIndex <= endIndex, the following combinations are not valid:
    //  b-a, c-a, c-b. The remaining a-a, a-b, a-c, b-b, b-c, c-c are handled below.

    if (startIndex >= this.startIndex && endIndex <= this.endIndex) {
      // Case b-b. Downloaded range is within the range of stored data. Nothing to do.
      return;
    }

    if (startIndex <= this.startIndex && endIndex >= this.endIndex) {
      //Case a-c. Downloaded data is superset of stored data. No need to cleanup existing data
      this.startIndex = startIndex;
      this.endIndex = endIndex;
      return;
    }

    if (endIndex < this.startIndex || startIndex > this.endIndex) {
      // Cases a-a and c-c. New data is not contiguous with stored data.
      // This means the current data needs to be thrown away.
      this.lines = {};
      this.startIndex = startIndex;
      this.endIndex = endIndex;
      return;
    }

    // Cases a-b and b-c. At least one of startIndex and endIndex is within the range of stored
    // data. The currently stored data needs to be cleaned up.
    if (this.isSelectionActive) {
      if (startIndex < this.startIndex) {
        // Case a-b.
        this.startIndex = startIndex;
      } else {
        // Case b-c.
        this.endIndex = endIndex;
      }
      return;
    }

    const overscanStartIndex = startIndex > destroyOverscanRowCount
      ? startIndex - destroyOverscanRowCount : 0;
    const overscanEndIndex = endIndex + destroyOverscanRowCount;

    if (startIndex < this.startIndex) {
      // Case a-b.
      this.startIndex = startIndex;
      this.cleanupLines(overscanStartIndex, overscanEndIndex);
    } else {
      // Case b-c.
      this.endIndex = endIndex;
      this.cleanupLines(overscanStartIndex, overscanEndIndex);
    }
  }

  addChunk(chunk: ParsedLogChunk) {
    this.chunks.splice(binarySearchGreater(this.chunks, chunk.firstLine, (ch, line) => ch.firstLine - line),
      0, chunk);
  }

  addLine(line: RenderedLogLine) {
    if (line.number in this.lines) {
      return;
    }
    this.lines[line.number] = line;
  }

  setLogNumLines(numLines: number) {
    this.logNumLines = numLines;
  }

  getCssClassesForChunk(chunk: ParsedLogChunk) {
    let cssClasses = this.chunkToCssClasses[chunk.firstLine];
    if (cssClasses === undefined) {
      cssClasses = parseCssClassesForChunk(chunk, chunk.firstLine, chunk.lastLine);
      this.chunkToCssClasses[chunk.firstLine] = cssClasses;
    }
    return cssClasses;
  }

  requestRows(info: RenderedRows) {
    if (info.overscanStartIndex >= this.startIndex &&
      info.overscanStopIndex <= this.endIndex) {
      return;
    }

    if (this.pendingRequest) {
      this.pendingRequest.promise.cancel();
    }

    const needFirstRow = info.overscanStartIndex > this.fetchOverscanRowCount
      ? info.overscanStartIndex - this.fetchOverscanRowCount : 0;
    const needLastRow = info.overscanStopIndex + this.fetchOverscanRowCount < this.logNumLines
      ? info.overscanStopIndex + this.fetchOverscanRowCount
      : this.logNumLines;

    let fetchFirstRow = needFirstRow;
    if (needFirstRow >= this.startIndex && needFirstRow < this.endIndex) {
      fetchFirstRow = this.endIndex;
    }
    let fetchLastRow = needLastRow;
    if (needLastRow >= this.startIndex && needLastRow < this.endIndex) {
      fetchLastRow = this.startIndex;
    }
    if (fetchFirstRow > fetchLastRow) {
      // Shouldn't happen
      return;
    }

    this.pendingRequest = {
      promise: this.accessor.getRaw(`logs/${this.logid}/contents`, {
        offset: fetchFirstRow,
        limit: fetchLastRow - fetchFirstRow
      }),
      startIndex: fetchFirstRow,
      endIndex: fetchLastRow,
    };
    this.pendingRequest.promise.then(response => {
      const content = response.logchunks[0].content as string;
      const chunk = parseLogChunk(fetchFirstRow, content, this.logType);
      this.addDownloadedRange(chunk.firstLine, chunk.lastLine,
        this.destroyOverscanRowCount);
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
