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
import {observer, useLocalObservable} from "mobx-react";
import {useDataAccessor} from "../../data/ReactUtils";
import {binarySearchLessEqual} from "../../util/BinarySearch";
import {
  AutoSizer as _AutoSizer,
  AutoSizerProps, defaultCellRangeRenderer,
  List as _List,
  ListProps,
  ListRowProps
} from 'react-virtualized';
import {RenderedRows} from "react-virtualized/dist/es/List";
import {digitCount} from "../../util/Math";
import {GridCellRangeProps} from "react-virtualized/dist/es/Grid";
import LogDownloadButton from "../LogDownloadButton/LogDownloadButton";
import {LogTextManager} from "./LogTextManager";

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

export type LogViewerProps = {
  log: Log;
  fetchOverscanRowCount: number;
  destroyOverscanRowCount: number;
}

const LogViewerText = observer(({log, fetchOverscanRowCount, destroyOverscanRowCount}: LogViewerProps) => {
  const accessor = useDataAccessor([]);
  const [, setRenderCounter] = useState(0);

  const manager = useLocalObservable(() =>
    new LogTextManager(accessor, log.logid, log.type, fetchOverscanRowCount, destroyOverscanRowCount,
      () => setRenderCounter(c => c + 1)));

  manager.setLogNumLines(log.num_lines);

  const logLineDigitCount = digitCount(log.num_lines);

  const renderEmptyRow = (row: ListRowProps) => {
    return <div key={row.index} className="bb-logviewer-text-row" style={row.style}></div>;
  }

  const renderRow = (row: ListRowProps) => {
    const renderedLine = manager.lines[row.index];
    if (renderedLine !== undefined) {
      return renderedLine.content;
    }

    const chunkIndex = binarySearchLessEqual(manager.chunks, row.index,
      (ch, index) => ch.firstLine - index);

    if (chunkIndex < 0 || chunkIndex >= manager.chunks.length) {
      return renderEmptyRow(row);
    }
    const chunk = manager.chunks[chunkIndex];
    if (row.index < chunk.firstLine || row.index >= chunk.lastLine) {
      return renderEmptyRow(row);
    }
    const lineIndexInChunk = row.index - chunk.firstLine;
    const lineType = chunk.lineTypes[lineIndexInChunk];
    const lineCssClasses = manager.getCssClassesForChunk(chunk)[lineIndexInChunk];
    const lineStartInChunk = chunk.textLineBounds[lineIndexInChunk];
    const lineEndInChunk = chunk.textLineBounds[lineIndexInChunk + 1];
    const lineContent = escapeClassesToHtml(chunk.text, lineStartInChunk, lineEndInChunk,
      lineCssClasses);

    const content = (
      <div key={row.index} className="bb-logviewer-text-row" style={row.style}>
        <span data-linenumber-content={String(row.index).padStart(logLineDigitCount, ' ')}
              className={`log_${lineType}`}>
          {lineContent}
        </span>
      </div>
    );

    manager.addLine({
      content: content,
      number: row.index
    })

    return content;
  };

  const renderNoRows = () => {
    return <>...</>;
  };

  const onRowsRendered = (info: RenderedRows) => {
    manager.requestRows(info);
  };

  const containerRef = useRef<HTMLDivElement>(null);
  const checkSelection = () => {
    manager.setIsSelectionActive(isSelectionActiveWithinElement(containerRef.current));
  };

  const cellRangeRenderer = (params: GridCellRangeProps) => {
    // Default cell renderer will not render rows that are not visible. This breaks selection
    // because not rendered React nodes will disappear from DOM and lose selection information.
    // If it is determined that a selection is active, then no rows will be removed from the
    // range of rows to render, thus ensuring that selection information is not lost.
    manager.onCellRangeRendered(params.rowStartIndex, params.rowStopIndex);
    if (manager.isSelectionActive) {
      params.rowStartIndex = manager.selectionStartIndex;
      params.rowStopIndex = manager.selectionEndIndex;
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
