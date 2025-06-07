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

import {buildbotGetSettings} from "buildbot-plugin-support";
import {Build} from "buildbot-data-js";
import {fillTemplate, parseTemplate} from "../../util/TemplateFormat";

export const getBuildLinkDisplayProperties = () => {
  const template = buildbotGetSettings().getStringSetting('Links.build_link_template');
  if (template === "")
    return [];
  return [...parseTemplate(template).replacements.values()]
    .filter(x => x.startsWith("prop:"))
    .map(x => x.substring(5));
}

export const formatBuildLinkText = (build: Build): string => {
  const template = buildbotGetSettings().getStringSetting('Links.build_link_template');
  if (template === "") {
    return `${build.number}`;
  }
  const replacements = new Map<string, string>([['build_number', `${build.number}`]]);
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