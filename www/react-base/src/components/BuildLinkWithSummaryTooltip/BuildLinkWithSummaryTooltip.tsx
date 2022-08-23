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

import './BuildLinkWithSummaryTooltip.less';
import {Link} from "react-router-dom";
import BuildSummaryTooltip from "../BuildSummaryTooltip/BuildSummaryTooltip";
import {OverlayTrigger, Tooltip} from "react-bootstrap";
import {Build} from "../../data/classes/Build";
import {results2class} from "../../util/Results";
import {observer} from "mobx-react";
import {Builder} from "../../data/classes/Builder";

type BuildLinkWithSummaryTooltipProps = {
  build: Build;
  builder?: Builder;
};

const BuildLinkWithSummaryTooltip = observer(({build, builder}: BuildLinkWithSummaryTooltipProps) => {

  const renderBuildTooltip = (props: {[p: string]: any}) => (
    <Tooltip className="buildsummarytooltipstyle" id="bb-tooltip-build" {...props}>
      <BuildSummaryTooltip build={build}/>
    </Tooltip>
  );

  const linkText = builder !== undefined
    ? <>{builder.name} / {build.number}</>
    : <>{build.number}</>

  return (
    <Link to={`/builders/${build.builderid.toString()}/builds/${build.number}`}>
      <OverlayTrigger trigger={["hover", "focus"]} delay={{ show: 250, hide: 400 }}
                      overlay={renderBuildTooltip} placement="right">
        <span className={"badge-status " + results2class(build, 'pulse')}>
          {linkText}
        </span>
      </OverlayTrigger>
    </Link>
  );
});

export default BuildLinkWithSummaryTooltip;
