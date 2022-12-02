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

import './LogViewerText.scss'
import {Log} from "../../data/classes/Log";
import {FC, useRef, useState} from 'react';
import {escapeClassesToHtml, generateStyleElement} from "../../util/AnsiEscapeCodes";
import {action, observable} from 'mobx';
import {observer, useLocalObservable} from "mobx-react";
import {useDataAccessor} from "../../data/ReactUtils";
import {binarySearchGreater, binarySearchLessEqual} from "../../util/BinarySearch";
import {CancellablePromise} from "../../util/CancellablePromise";
import {
  AutoSizer as _AutoSizer,
  AutoSizerProps, defaultCellRangeRenderer,
  List as _List,
  ListProps,
  ListRowProps
} from 'react-virtualized';
import {RenderedRows} from "react-virtualized/dist/es/List";
import {ParsedLogChunk, parseLogChunk} from "../../util/LogChunkParsing";
import {digitCount} from "../../util/Math";
import {GridCellRangeProps} from "react-virtualized/dist/es/Grid";
import LogDownloadButton from "../LogDownloadButton/LogDownloadButton";

const List = _List as unknown as FC<ListProps>;
const AutoSizer = _AutoSizer as unknown as FC<AutoSizerProps>;

const isSelectionActiveWithinElement = (element: HTMLElement | null | undefined) => {
  if (element === null || element === undefined) {
    return false;
  }
  const selection = window.getSelection();
  if (selection === null || selection.type !== "Range" || selection.anchorNode === null ||
    selection.focusNode === null) {
    return false;
  }

  return element.contains(selection.anchorNode) || element.contains(selection.focusNode);
}

type RenderedLogLine = {
  content: JSX.Element | JSX.Element[];
  number: number;
}

class LogViewerState {
  lines = observable.map<number, RenderedLogLine>();
  chunks: ParsedLogChunk[] = [];

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
}

export type PendingRequest = {
  promise: CancellablePromise<any>;
  startIndex: number;
  endIndex: number;
}

export type LogViewerProps = {
  log: Log;
  fetchOverscanRowCount: number;
  destroyOverscanRowCount: number;
}

const LogViewerText = observer(({log, fetchOverscanRowCount, destroyOverscanRowCount}: LogViewerProps) => {
  const viewerState = useLocalObservable(() => new LogViewerState());
  const accessor = useDataAccessor([]);

  const pendingRequest = useRef<PendingRequest | null>(null);
  const logLineDigitCount = digitCount(log.num_lines);

  // Used to refresh displayed data when the log is downloaded and line state changes
  const [renderCounter, setRenderCounter] = useState(0);

  const renderEmptyRow = (row: ListRowProps) => {
    return <div key={row.index} className="bb-logviewer-text-row" style={row.style}></div>;
  }

  const renderRow = (row: ListRowProps) => {
    const renderedLine = viewerState.lines.get(row.index);
    if (renderedLine !== undefined) {
      return renderedLine.content;
    }

    const chunkIndex = binarySearchLessEqual(viewerState.chunks, row.index,
      (ch, index) => ch.firstLine - index);

    if (chunkIndex < 0 || chunkIndex >= viewerState.chunks.length) {
      return renderEmptyRow(row);
    }
    const chunk = viewerState.chunks[chunkIndex];
    if (row.index < chunk.firstLine || row.index >= chunk.lastLine) {
      return renderEmptyRow(row);
    }
    const lineIndexInChunk = row.index - chunk.firstLine;
    const lineType = chunk.lineTypes[lineIndexInChunk];
    const lineCssClasses = chunk.cssClasses[lineIndexInChunk];
    const lineStartInChunk = chunk.lineBounds[lineIndexInChunk];
    const lineEndInChunk = chunk.lineBounds[lineIndexInChunk + 1];
    const lineContent = escapeClassesToHtml(chunk.visibleText, lineStartInChunk, lineEndInChunk,
      lineCssClasses);

    const content = (
      <div key={row.index} className="bb-logviewer-text-row" style={row.style}>
        <span data-linenumber-content={String(row.index).padStart(logLineDigitCount, ' ')}
              className={`log_${lineType}`}>
          {lineContent}
        </span>
      </div>
    );

    viewerState.addLine({
      content: content,
      number: row.index
    })

    return content;
  };

  const renderNoRows = () => {
    return <>...</>;
  };

  const onRowsRendered = (info: RenderedRows) => {
    if (info.overscanStartIndex >= viewerState.startIndex &&
        info.overscanStopIndex <= viewerState.endIndex) {
      return;
    }

    if (pendingRequest.current) {
      pendingRequest.current.promise.cancel();
    }

    const needFirstRow = info.overscanStartIndex > fetchOverscanRowCount
      ? info.overscanStartIndex - fetchOverscanRowCount : 0;
    const needLastRow = info.overscanStopIndex + fetchOverscanRowCount < log.num_lines
      ? info.overscanStopIndex + fetchOverscanRowCount
      : log.num_lines;

    let fetchFirstRow = needFirstRow;
    if (needFirstRow >= viewerState.startIndex && needFirstRow < viewerState.endIndex) {
      fetchFirstRow = viewerState.endIndex;
    }
    let fetchLastRow = needLastRow;
    if (needLastRow >= viewerState.startIndex && needLastRow < viewerState.endIndex) {
      fetchLastRow = viewerState.startIndex;
    }
    if (fetchFirstRow > fetchLastRow) {
      // Shouldn't happen
      return;
    }

    pendingRequest.current = {
      promise: accessor.getRaw(`logs/${log.logid}/contents`, {
        offset: fetchFirstRow,
        limit: fetchLastRow - fetchFirstRow
      }),
      startIndex: fetchFirstRow,
      endIndex: fetchLastRow,
    };
    pendingRequest.current?.promise.then(response => {
      const content = response.logchunks[0].content as string;
      const lines = content.split("\n");

      // There is a trailing '\n' that generates an empty line in the end
      if (lines.length > 1) {
        lines.pop();
      }

      const chunk = parseLogChunk(fetchFirstRow, content, log.type);
      viewerState.addDownloadedRange(chunk.firstLine, chunk.lastLine,
        destroyOverscanRowCount);
      viewerState.addChunk(chunk);
      setRenderCounter(counter => counter + 1);
    })
  };

  const containerRef = useRef<HTMLDivElement>(null);
  const checkSelection = () => {
    viewerState.setIsSelectionActive(isSelectionActiveWithinElement(containerRef.current));
  };

  const cellRangeRenderer = (params: GridCellRangeProps) => {
    // Default cell renderer will not render rows that are not visible. This breaks selection
    // because not rendered React nodes will disappear from DOM and lose selection information.
    // If it is determined that a selection is active, then no rows will be removed from the
    // range of rows to render, thus ensuring that selection information is not lost.
    viewerState.onCellRangeRendered(params.rowStartIndex, params.rowStopIndex);
    if (viewerState.isSelectionActive) {
      params.rowStartIndex = viewerState.selectionStartIndex;
      params.rowStopIndex = viewerState.selectionEndIndex;
    }
    return defaultCellRangeRenderer(params);
  }

  return (
    <>
      {generateStyleElement(".bb-logviewer-text-area")}
      <AutoSizer>
        {({height, width}) => (
          <div className="bb-logviewer-text-area" ref={containerRef}>
            <div className="bb-logviewer-text-download-log">
              <div>
                <LogDownloadButton log={log}/>
              </div>
            </div>
            <List
              className="bb-logviewer-text-area"
              rowCount={log.num_lines}
              rowRenderer={row => renderRow(row)}
              onRowsRendered={onRowsRendered}
              noRowsRenderer={renderNoRows}
              height={height}
              width={width}
              rowHeight={18}
              renderCounter={renderCounter}
              cellRangeRenderer={cellRangeRenderer}
              containerProps={{
                onMouseDown: () => checkSelection(),
                onMouseUp: () => checkSelection(),
              }}
            />
          </div>
        )}
      </AutoSizer>
    </>
  );
});

export default LogViewerText;
