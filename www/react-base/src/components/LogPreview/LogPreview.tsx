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

import './LogPreview.scss';
import {Card} from "react-bootstrap";
import {Link} from "react-router-dom";
import {Log} from "../../data/classes/Log";
import {globalSettings} from "../../plugins/GlobalSettings";
import {useEffect, useRef, useState} from 'react';
import ArrowExpander from "../ArrowExpander/ArrowExpander";
import {ansi2html, generateStyleElement} from "../../util/AnsiEscapeCodes";
import {action, makeObservable, observable} from 'mobx';
import {useLocalObservable} from "mobx-react";
import {useDataAccessor} from "../../data/ReactUtils";
import {CancellablePromise} from "../../util/CancellablePromise";
import {useStateWithDefaultIfNotSet} from "../../util/React";
import LogDownloadButton from "../LogDownloadButton/LogDownloadButton";

type RenderedLogLine = {
  content: JSX.Element[];
  class: string;
  number: number;
}

class LogPreviewState {
  lines = observable.array<RenderedLogLine>();
  @observable maxNumber: number = 0;

  constructor() {
    makeObservable(this);
  }

  @action clearLines() {
    this.maxNumber = 0;
    this.lines.clear();
  }

  @action addLine(line: RenderedLogLine) {
    if (line.number <= this.maxNumber) {
      return;
    }

    this.lines.push(line);
    this.maxNumber = line.number;
  }

  @action sortLines(maxLines: number) {
    this.lines.sort((a, b) => a.number - b.number);
    this.lines.splice(0, this.lines.length - maxLines);
  }
}

export type LogPreviewProps = {
  builderid: number;
  buildnumber: number;
  stepnumber: number;
  log: Log;
  initialFullDisplay: boolean;
}

const LogPreview = ({builderid, buildnumber, stepnumber, log,
                     initialFullDisplay}: LogPreviewProps) => {
  const previewState = useLocalObservable(() => new LogPreviewState());

  const initialLoadLines = globalSettings.getIntegerSetting('LogPreview.loadlines');
  const maximumLoadLines = globalSettings.getIntegerSetting('LogPreview.maxlines');

  const [fullDisplay, setFullDisplay] = useStateWithDefaultIfNotSet(() => initialFullDisplay);

  const accessor = useDataAccessor([builderid, buildnumber, stepnumber, log.id]);

  const [htmlLog, setHtmlLog] = useState('');

  const pendingRequest = useRef<CancellablePromise<any> | null>(null);

  useEffect(() => {
    if (!fullDisplay) {
      previewState.clearLines();
      return;
    }

    if (log.type === 'h') {
      if (pendingRequest.current !== null) {
        pendingRequest.current.cancel()
      }

      pendingRequest.current = accessor.getRaw(`logs/${log.logid}/contents`, {});
      pendingRequest.current.then(content => {
        setHtmlLog(content.logchunks[0].content);
      });
    } else {
      {
        let limit = 0;
        let offset = 0;

        const lineCountLimit = previewState.lines.length === 0
          ? initialLoadLines : maximumLoadLines;
        const firstLineToLoad = previewState.lines.length === 0
          ? 0 : previewState.maxNumber + 1;

        if (log.num_lines - firstLineToLoad <= lineCountLimit) {
          offset = firstLineToLoad;
          limit = log.num_lines;
        } else {
          offset = log.num_lines - lineCountLimit
          limit = lineCountLimit
        }

        if (limit === 0) {
          return;
        }

        pendingRequest.current = accessor.getRaw(`logs/${log.logid}/contents`, {
          offset: offset,
          limit: limit
        });

        pendingRequest.current.then(response => {
          const content = response.logchunks[0].content as string;
          const lines = content.split("\n");

          // there is a trailing '\n' that generates an empty line in the end
          if (lines.length > 1) {
            lines.pop();
          }

          let number = offset;
          for (let line of lines) {
            let logclass = "o";
            if ((line.length > 0) && (log.type === 's')) {
              logclass = line[0];
              line = line.slice(1);
            }
            // we just push the lines in the end, and will apply sort eventually
            previewState.addLine({
              content: ansi2html(line),
              class: `log_${logclass}`,
              number: number
            });
            number += 1;
          }
          previewState.sortLines(maximumLoadLines);
        });
      };
    }

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [log.num_lines, fullDisplay]);

  const renderLogContent = () => {
    if (log.type === 'h') {
      return (
        <Card.Body dangerouslySetInnerHTML={{__html: htmlLog}}/>
      );
    }

    const lineElements = previewState.lines.map(line => {
      return (
        <div key={line.number} className="logline">
          <span data-linenumber-content={line.number} className={`${line.class}`}>
            {line.content}
          </span>
        </div>
      );
    });

    return (
      <pre className="bb-log-preview-contents select-content log">
        {lineElements}
      </pre>
    );
  }

  return (
    <Card bg={log.name === 'err.html' ? 'danger' : 'light'} className="logpreview">
      {generateStyleElement("pre.log")}
      <Card.Header>
        <div className="flex-row">
          <div onClick={() => setFullDisplay(!fullDisplay)} className="flex-grow-3">
            <ArrowExpander isExpanded={fullDisplay}/>
            &nbsp;
            {log.name}
          </div>
          <div className="flex-grow-1">
            <div className="pull-right">
              <Link to={`/builders/${builderid}/builds/${buildnumber}/steps/${stepnumber}/logs/${log.slug}`}>
                view all {log.num_lines} line{log.num_lines > 1 ? 's' : ''}&nbsp;
              </Link>
              <LogDownloadButton log={log}/>
            </div>
          </div>
        </div>
      </Card.Header>
      {fullDisplay ? <div>{renderLogContent()}</div> : <></>}
    </Card>
  );
}

export default LogPreview;

globalSettings.addGroup({
  name: 'LogPreview',
  caption: 'LogPreview related settings',
  items: [{
      type: 'integer',
      name: 'loadlines',
      caption: 'Initial number of lines to load',
      defaultValue: 40
    }, {
      type: 'integer',
      name: 'maxlines',
      caption: 'Maximum number of lines to show',
      defaultValue: 40
    }, {
      type: 'string',
      name: 'expand_logs',
      caption: 'Expand logs with these names (use ; as separator)',
      defaultValue: 'summary'
    }
  ]});
