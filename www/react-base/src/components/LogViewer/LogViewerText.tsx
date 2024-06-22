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
import {forwardRef, useCallback, useMemo, useRef, useState} from 'react';
import {useHotkeys} from "react-hotkeys-hook";
import {generateStyleElement} from "../../util/AnsiEscapeCodes";
import {observer} from "mobx-react";
import {Log, useDataAccessor} from "buildbot-data-js";
import {FixedSizeList, ListOnItemsRenderedProps, FixedSizeListOuterProps} from 'buildbot-ui';
import AutoSizer, {Size} from "react-virtualized-auto-sizer";
import {digitCount} from "../../util/Math";
import {LogDownloadButtons} from "../LogDownloadButtons/LogDownloadButtons";
import {LogSearchField} from "../LogSearchField/LogSearchField";
import {LogTextManager} from "./LogTextManager";
import {LogViewerTextLineRenderer} from "./LogViewerTextLineRenderer";

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
  downloadInitiateOverscanRowCount: number;
  downloadOverscanRowCount: number;
  cachedDownloadOverscanRowCount: number;
  cacheRenderedOverscanRowCount: number;
  maxChunkLinesCount: number;
}

export const LogViewerText = observer(({log, downloadInitiateOverscanRowCount, downloadOverscanRowCount,
                                        cachedDownloadOverscanRowCount, cacheRenderedOverscanRowCount,
                                        maxChunkLinesCount}: LogViewerProps) => {
  const accessor = useDataAccessor([]);
  const [, setRenderCounter] = useState(0);

  const managerRef = useRef<LogTextManager|null>(null);
  if (managerRef.current === null) {
    managerRef.current = new LogTextManager(
        (offset, limit) => accessor.getRaw(`logs/${log.logid}/contents`, {
          offset: offset,
          limit: limit,
        }),
        log.type, downloadInitiateOverscanRowCount,
        downloadOverscanRowCount, cachedDownloadOverscanRowCount, cacheRenderedOverscanRowCount,
        maxChunkLinesCount, () => setRenderCounter(c => c + 1));
  }
  const manager = managerRef.current!;

  manager.setLogNumLines(log.num_lines);

  const logLineDigitCount = digitCount(log.num_lines);

  const onRowsRendered = (info: ListOnItemsRenderedProps) => {
    manager.requestRows(info);
  };

  const containerRef = useRef<HTMLDivElement>(null);
  const checkSelection = useCallback(() => {
    manager.setIsSelectionActive(isSelectionActiveWithinElement(containerRef.current));
  }, []);

  const getRangeToRenderOverride = (overscanStartIndex: number,
                                    overscanStopIndex: number,
                                    visibleStartIndex: number,
                                    visibleStopIndex: number): [number, number, number, number] => {
    // Default cell renderer will not render rows that are not visible. This breaks selection
    // because not rendered React nodes will disappear from DOM and lose selection information.
    // If it is determined that a selection is active, then no rows will be removed from the
    // range of rows to render, thus ensuring that selection information is not lost.
    manager.onCellRangeRendered(overscanStartIndex, overscanStopIndex);
    if (manager.isSelectionActive) {
      overscanStartIndex = manager.selectionStartIndex;
      overscanStopIndex = manager.selectionEndIndex;
    }
    return [overscanStartIndex, overscanStopIndex, visibleStartIndex, visibleStopIndex];
  }

  const onSearchInputChanged = (text: string, caseSensitive: boolean, useRegex: boolean) => {
    manager.setSearchString(text === '' ? null : text);
    manager.setSearchCaseSensitivity(caseSensitive);
    manager.setUseRegex(useRegex);
  }

  const listRef = useRef<FixedSizeList<any>>(null);
  const currentSearchResultLineRef = useRef<number>(-1);
  const currentSearchResultLine = manager.getCurrentSearchResultLine();
  if (currentSearchResultLineRef.current !== currentSearchResultLine && listRef.current !== null) {
    currentSearchResultLineRef.current = currentSearchResultLine;
    setRenderCounter(c => {
      // scrollToItem will
      listRef.current!.scrollToItem(currentSearchResultLine);
      return c + 1;
    });
  }

  const searchInputRef = useRef<HTMLInputElement>(null);
  useHotkeys('Mod+F', () => { searchInputRef.current?.focus(); }, {preventDefault: true});

  const outerElementType = useMemo(() => forwardRef<HTMLDivElement, FixedSizeListOuterProps>(
    (props, ref) => (
    <div ref={ref} onMouseDown={checkSelection} onMouseUp={checkSelection} {...props}/>
  )), []);

  const LogTextArea: React.FC<Size> = ({height, width}) => (
    <div className="bb-logviewer-text-area" ref={containerRef}>
      <div className="bb-logviewer-text-download-log">
        <div>
          <LogSearchField currentResult={manager.currentSearchResultIndex + 1}
                          totalResults={Math.max(manager.totalSearchResultCount, 0)}
                          onSearchInputChanged={onSearchInputChanged}
                          onPrevClicked={() => manager.setPrevSearchResult()}
                          onNextClicked={() => manager.setNextSearchResult()}
                          inputRef={searchInputRef}/>
          <LogDownloadButtons log={log}/>
        </div>
      </div>
      <FixedSizeList
        className="bb-logviewer-text-area"
        ref={listRef}
        itemCount={log.num_lines}
        onItemsRendered={onRowsRendered}
        height={height}
        width={width}
        itemSize={18}
        getRangeToRenderOverride={getRangeToRenderOverride}
        onCacheClear={() => manager.clearCache()}
        outerElementType={outerElementType}
      >
        {({index, style}) => (
          LogViewerTextLineRenderer({manager: manager, logLineDigitCount: logLineDigitCount,
            style: style, index: index})
        )
        }
      </FixedSizeList>
    </div>
  );

  return (
    <>
      {generateStyleElement(".bb-logviewer-text-area")}
      <AutoSizer>
        {LogTextArea}
      </AutoSizer>
    </>
  );
});
