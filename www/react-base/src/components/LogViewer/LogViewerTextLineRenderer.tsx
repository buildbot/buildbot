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

import {LogTextManager} from "./LogTextManager";

export type LogViewerTextLineRendererProps = {
  manager: LogTextManager;
  logLineDigitCount: number;
  style: React.CSSProperties;
  index: number;
};

export const LogViewerTextLineRenderer = ({manager, logLineDigitCount,
                                           style, index}: LogViewerTextLineRendererProps) => {
  const renderEmptyRowContents = (index: number, style: React.CSSProperties) => {
    return <div key={index} className="bb-logviewer-text-row" style={style}></div>;
  }

  const renderRowContents = (index: number, lineType: string, style: React.CSSProperties,
                             content: JSX.Element[]) => {
    return (
      <div key={index} className="bb-logviewer-text-row" style={style}>
        <span data-linenumber-content={String(index + 1).padStart(logLineDigitCount, ' ')}
              className={`log_${lineType}`}>
          {content}
        </span>
      </div>
    );
  };

  return manager.getRenderedLineContent(index, style,
    renderRowContents, renderEmptyRowContents);
}
