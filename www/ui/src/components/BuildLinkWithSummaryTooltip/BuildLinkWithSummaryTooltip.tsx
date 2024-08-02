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
import {buildbotGetSettings, buildbotSetupPlugin} from "buildbot-plugin-support";
import {observer} from "mobx-react";
import {Builder} from "buildbot-data-js";
import {fillTemplate, parseTemplate} from "../../util/TemplateFormat";
import {BuildSummaryTooltip} from "../BuildSummaryTooltip/BuildSummaryTooltip";
import {BadgeRound} from "../BadgeRound/BadgeRound";

type BuildLinkWithSummaryTooltipProps = {
  build: Build;
  builder?: Builder | null;
};

export const getBuildLinkDisplayProperties = () => {
  var template = buildbotGetSettings().getStringSetting('Links.build_link_template');
  if (template === "")
    return [];
  return [...parseTemplate(template).replacements.values()]
    .filter(x => x.startsWith("prop:"))
    .map(x => x.substring(5));
}

export const formatBuildLinkText = (build: Build): string => {
  var template = buildbotGetSettings().getStringSetting('Links.build_link_template');
  if (template === "") {
    return `${build.number}`;
  }
  var replacements = new Map<string, string>([['build_number', `${build.number}`]]);
  for (const repl of parseTemplate(template).replacements.values()) {
    if (repl.startsWith("prop:")) {
      const prop = repl.substring(5);
      const value = build.properties[prop];
      if (value === undefined || value === null || value === '') {
        continue;
      }
      replacements.set(repl, value[0]);
    }
  }

  return fillTemplate(template, replacements);
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

  const buildText = formatBuildLinkText(build);

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

buildbotSetupPlugin((reg) => {
  reg.registerSettingGroup({
    name: 'Links',
    caption: 'Settings related to links between pages',
    items: [{
      type: 'string',
      name: 'build_link_template',
      caption: 'Format of data displayed in build badges. Use %(prop:build_property) to include ' +
        'build properties, %(build_number) to include build number',
      defaultValue: '%(prop:branch) (%(build_number))'
    }
  ]});
});
