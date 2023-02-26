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


import {action, observable} from "mobx";
import {binarySearchGreater} from "../../util/BinarySearch";
import {ChunkCssClasses, parseCssClassesForChunk, ParsedLogChunk} from "../../util/LogChunkParsing";

export type RenderedLogLine = {
  content: JSX.Element | JSX.Element[];
  number: number;
}

export class LogTextManager {
  lines = observable.map<number, RenderedLogLine>();
  chunks: ParsedLogChunk[] = []; // not observable
  chunkToCssClasses: {[firstLine: string]: ChunkCssClasses} = {}; // not observable

  startIndex = 0; // not observable
  endIndex = 0; // not observable

  // Ensures that when a selection is active no rows are removed from the set of nodes rendered
  // by React. Otherwise removed nodes will break selection.
  isSelectionActive = false; // not observable
  selectionStartIndex = 0; // not observable
  selectionEndIndex = 0; // not observable

  lastRenderStartIndex = 0; // not observable
  lastRenderEndIndex = 0; // not observable

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

  @action cleanupLines(targetStartIndex: number, targetEndIndex: number) {
    if (targetStartIndex > this.endIndex) {
      this.startIndex = targetStartIndex;
      this.endIndex = targetStartIndex;
      this.lines.clear();
      return;
    }

    if (targetEndIndex < this.startIndex) {
      this.startIndex = targetEndIndex;
      this.endIndex = targetEndIndex;
      this.lines.clear();
      return;
    }

    if (this.startIndex < targetStartIndex) {
      for (let i = this.startIndex; i < targetStartIndex; ++i) {
        this.lines.delete(i);
      }
      this.startIndex = targetStartIndex;
    }
    if (targetEndIndex < this.endIndex) {
      for (let i = targetEndIndex; i < this.endIndex; ++i) {
        this.lines.delete(i);
      }
      this.endIndex = targetEndIndex;
    }
  }

  @action addDownloadedRange(startIndex: number, endIndex: number,
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
      this.lines.clear();
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

  @action addChunk(chunk: ParsedLogChunk) {
    this.chunks.splice(binarySearchGreater(this.chunks, chunk.firstLine, (ch, line) => ch.firstLine - line),
      0, chunk);
  }

  @action addLine(line: RenderedLogLine) {
    if (this.lines.has(line.number)) {
      return;
    }
    this.lines.set(line.number, line);
  }

  getCssClassesForChunk(chunk: ParsedLogChunk) {
    let cssClasses = this.chunkToCssClasses[chunk.firstLine];
    if (cssClasses === undefined) {
      cssClasses = parseCssClassesForChunk(chunk, chunk.firstLine, chunk.lastLine);
      this.chunkToCssClasses[chunk.firstLine] = cssClasses;
    }
    return cssClasses;
  }
}
