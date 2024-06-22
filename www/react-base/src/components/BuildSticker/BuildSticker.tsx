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

import './BuildSticker.scss';
import {observer} from "mobx-react";
import {Link} from "react-router-dom";
import { Card } from 'react-bootstrap';
import {Build, Builder, results2class, results2text} from "buildbot-data-js";
import {BadgeStatus, durationFormat, useCurrentTime} from "buildbot-ui";

type BuildStickerProps = {
  build: Build;
  builder: Builder;
}

export const BuildSticker = observer(({build, builder}: BuildStickerProps) => {
  const now = useCurrentTime();

  return (
    <Card className={"bb-buildsticker " + results2class(build, null)}>
      <Card.Body>
        <div className="bb-buildsticker-left">
          <BadgeStatus className={results2class(build, null)}>
            {results2text(build)}
          </BadgeStatus>
          <Link to={`builders/${builder.builderid}/builds/${build.number}`}>
            {builder.name}/{build.number}
          </Link>
        </div>
        <div className="bb-buildsticker-left">
          <span className="bb-buildsticker-time">
            {durationFormat((build.complete ? build.complete_at! : now) - build.started_at)}
          </span>
          <span>{build.state_string}</span>
        </div>
      </Card.Body>
    </Card>
  );
});
