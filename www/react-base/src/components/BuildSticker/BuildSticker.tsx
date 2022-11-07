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

import './BuildSticker.less'
import {Build} from "../../data/classes/Build";
import {Builder} from "../../data/classes/Builder";
import {results2class, results2text} from "../../util/Results";
import {Link} from "react-router-dom";
import {durationFormat, useCurrentTime} from "../../util/Moment";

type BuildStickerProps = {
  build: Build;
  builder: Builder;
}

const BuildSticker = ({build, builder}: BuildStickerProps) => {
  const now = useCurrentTime();

  return (
    <div className={"panel panel-default buildsticker " + results2class(build, null)}>
      <div className="panel-body no-select">
        <div className="row">
          <span className={"pull-right label " + results2class(build, null)}>
            {results2text(build)}
          </span>
          <Link to={`builders/${builder.builderid}/builds/${build.number}`}>
            {builder.name}/{build.number}
          </Link>
        </div>
        <div className="row">
          <span className="pull-right">
            {durationFormat((build.complete ? build.complete_at! : now) - build.started_at)}
          </span>
          <span>{build.state_string}</span>
        </div>
      </div>
    </div>
  );
}

export default BuildSticker;