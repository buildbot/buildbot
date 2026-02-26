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

import './LogDownloadButtons.scss';
import {useContext, useState} from 'react';
import {Button, ButtonGroup} from 'react-bootstrap';
import {FaCopy, FaCheck, FaDownload} from 'react-icons/fa';
import {DataClientContext, Log} from 'buildbot-data-js';

export type LogDownloadButtonsProps = {
  log: Log;
};

export const LogDownloadButtons = ({log}: LogDownloadButtonsProps) => {
  const dataClient = useContext(DataClientContext);
  const apiRootUrl = dataClient.restClient.rootUrl;
  const [copied, setCopied] = useState(false);

  const handleCopyToClipboard = async () => {
    try {
      const response = await fetch(new URL(`logs/${log.id}/raw`, apiRootUrl).toString());
      const text = await response.text();
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.error('Failed to copy log to clipboard', e);
    }
  };

  return (
    <ButtonGroup>
      <Button
        href={new URL(`logs/${log.id}/raw`, apiRootUrl).toString()}
        variant="default"
        title="download log"
        className="bb-log-download-button btn-sm"
      >
        <FaDownload />
      </Button>
      <Button
        variant="default"
        title={copied ? 'copied!' : 'copy log to clipboard'}
        className="bb-log-download-button btn-sm"
        onClick={() => {
          void handleCopyToClipboard();
        }}
      >
        {copied ? <FaCheck /> : <FaCopy />}
      </Button>
      <Button
        href={new URL(`logs/${log.id}/raw_inline`, apiRootUrl).toString()}
        variant="default"
        title="show log"
        className="bb-log-download-button btn-sm"
      >
        Raw
      </Button>
    </ButtonGroup>
  );
};
