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

import './BuildLinkWithSummaryTooltip.scss';
import {Link} from "react-router-dom";
import BuildSummaryTooltip from "../BuildSummaryTooltip/BuildSummaryTooltip";
import {OverlayTrigger, Tooltip} from "react-bootstrap";
import {Build} from "../../data/classes/Build";
import {results2class} from "../../util/Results";
import {observer} from "mobx-react";
import {Builder} from "../../data/classes/Builder";
import BadgeRound from "../BadgeRound/BadgeRound";

type BuildLinkWithSummaryTooltipProps = {
  build: Build;
  builder?: Builder | null;
};

const BuildLinkWithSummaryTooltip = observer(({build, builder}: BuildLinkWithSummaryTooltipProps) => {

  if (builder === null) {
    builder = undefined;
  }

  const renderBuildTooltip = (props: {[p: string]: any}) => (
    <Tooltip className={"buildsummarytooltipstyle " + results2class(build, null)}
             id="bb-tooltip-build" {...props}>
      <BuildSummaryTooltip build={build}/>
    </Tooltip>
  );

  const buildText = ('branch' in build.properties) && (build.properties['branch'][0] !== null) &&
                    (build.properties['branch'][0] !== "")
    ? `${build.properties['branch'][0]} (${build.number})`
    : `${build.number}`;

  const linkText = builder !== undefined
    ? `${builder.name} / ${buildText}`
    : buildText

  return (
    <Link to={`/builders/${build.builderid.toString()}/builds/${build.number}`}>
      <OverlayTrigger trigger={["hover", "focus"]} delay={{ show: 250, hide: 400 }}
                      overlay={renderBuildTooltip} placement="right">
        <BadgeRound className={results2class(build, 'pulse')}>
          {linkText}
        </BadgeRound>
      </OverlayTrigger>
    </Link>
  );
});

export default BuildLinkWithSummaryTooltip;
