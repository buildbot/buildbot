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
import {OverlayTrigger, Tooltip} from "react-bootstrap";
import {Build, results2class} from "buildbot-data-js";
import {observer} from "mobx-react";
import {Builder} from "buildbot-data-js";
import {BuildSummaryTooltip} from "../BuildSummaryTooltip/BuildSummaryTooltip";
import {BadgeRound} from "../BadgeRound/BadgeRound";

type BuildLinkWithSummaryTooltipProps = {
  build: Build;
  builder?: Builder | null;
};

let extra_properties : string[] | null  = null;

export function SetBuildLinkExtraProperties(property_names: string[] | null) {
  if (property_names == null || property_names.length == 0) {
    extra_properties = null;
    return;
  }

  extra_properties = property_names;
}

export function GetBuildLinkExtraPropertiesList() : string[] {
  return extra_properties || [];
}

function ProduceBuildNumber(build: Build): string | number {
  if (extra_properties == null) {
    return build.number;
  }

  let build_number = "";
  for (const property_name of extra_properties) {
    if (!(property_name in build.properties)) {
      return build.number;
    }
    build_number += build.properties[property_name][0];
  }
  return build_number;  
}

export const BuildLinkWithSummaryTooltip =
  observer(({build, builder}: BuildLinkWithSummaryTooltipProps) => {

  if (builder === null) {
    builder = undefined;
  }

  const renderBuildTooltip = (props: {[p: string]: any}) => (
    <Tooltip className={"buildsummarytooltipstyle " + results2class(build, null)}
             id="bb-tooltip-build" {...props}>
      <BuildSummaryTooltip build={build}/>
    </Tooltip>
  );
  
  const build_number = ProduceBuildNumber(build);

  const buildText = ('branch' in build.properties) && (build.properties['branch'][0] !== null) &&
                    (build.properties['branch'][0] !== "")
    ? `${build.properties['branch'][0]} (${build_number})`
    : `${build_number}`;

  const linkText = builder !== undefined
    ? `${builder.name} / ${buildText}`
    : buildText

  return (
    <Link to={`/builders/${build.builderid.toString()}/builds/${build.number}`}>
      <OverlayTrigger trigger={["hover", "focus"]} delay={{ show: 250, hide: 400 }}
                      overlay={renderBuildTooltip} placement="right">
        <BadgeRound data-bb-test-id="build-link" className={results2class(build, 'pulse')}>
          {linkText}
        </BadgeRound>
      </OverlayTrigger>
    </Link>
  );
});
