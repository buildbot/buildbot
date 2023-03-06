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

import './LogDownloadButton.scss';
import {useContext} from "react";
import {FaDownload} from "react-icons/fa";
import {Log} from "../../data/classes/Log";
import {DataClientContext} from "../../data/ReactUtils";

export type LogDownloadButtonProps = {
  log: Log;
}

const LogDownloadButton = ({log}: LogDownloadButtonProps) => {
  const dataClient = useContext(DataClientContext);
  const apiRootUrl = dataClient.restClient.rootUrl;

  return (
    <a href={`${apiRootUrl}/logs/${log.id}/raw`} title="download log"
       className="btn btn-default btn-xs bb-log-download-button">
      <FaDownload/>&nbsp;
      Download
    </a>
  );
}

export default LogDownloadButton;
