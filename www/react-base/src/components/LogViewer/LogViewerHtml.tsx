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

import {Log} from "../../data/classes/Log";
import {useEffect, useRef, useState} from 'react';
import {useDataAccessor} from "../../data/ReactUtils";
import {CancellablePromise} from "../../util/CancellablePromise";
import {Card} from "react-bootstrap";

export type LogViewerHtmlProps = {
  log: Log;
}

const LogViewerHtml = ({log}: LogViewerHtmlProps) => {
  const accessor = useDataAccessor([]);
  const [htmlLog, setHtmlLog] = useState('');
  const pendingRequest = useRef<CancellablePromise<any> | null>(null);

  useEffect(() => {
    if (log.type !== 'h') {
      console.log("LogViewerHtml can only be used with html logs");
      return;
    }
    if (pendingRequest.current !== null) {
      pendingRequest.current.cancel()
    }

    pendingRequest.current = accessor.getRaw(`logs/${log.logid}/contents`, {});
    pendingRequest.current.then(content => {
      setHtmlLog(content.logchunks[0].content);
    });

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Card.Body dangerouslySetInnerHTML={{__html: htmlLog}}/>
  );
}

export default LogViewerHtml;
