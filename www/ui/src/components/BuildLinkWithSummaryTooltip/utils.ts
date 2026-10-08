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

import {buildbotGetSettings} from 'buildbot-plugin-support';
import {Build} from 'buildbot-data-js';
import {fillTemplate, parseTemplate} from '../../util/TemplateFormat';

export const defaultBuildLinkTemplate = '%(prop:branch) (%(build_number))';

export const getBuildLinkDisplayProperties = () => {
  const template = buildbotGetSettings().getStringSetting('Links.build_link_template');
  if (template === '') return [];
  return [...parseTemplate(template).replacements.values()]
    .filter((x) => x.startsWith('prop:'))
    .map((x) => x.substring(5));
};

const getBuildPropertyValue = (build: Build, prop: string): string | null => {
  const value = build.properties[prop];
  if (value === undefined || value === null || value === '') {
    return null;
  }
  const propValue = Array.isArray(value) ? value[0] : value;
  if (propValue === undefined || propValue === null || propValue === '') {
    return null;
  }
  return `${propValue}`;
};

export const formatBuildLinkTextWithTemplate = (build: Build, template: string): string => {
  if (template === '') {
    return `${build.number}`;
  }

  if (template === defaultBuildLinkTemplate) {
    const branch = getBuildPropertyValue(build, 'branch');
    if (branch === null) {
      return `${build.number}`;
    }
    return `${branch} (${build.number})`;
  }

  const replacements = new Map<string, string>([['build_number', `${build.number}`]]);
  for (const repl of parseTemplate(template).replacements.values()) {
    if (repl.startsWith('prop:')) {
      const prop = repl.substring(5);
      const value = getBuildPropertyValue(build, prop);
      if (value === null) {
        continue;
      }
      replacements.set(repl, value);
    }
  }

  return fillTemplate(template, replacements);
};

export const formatBuildLinkText = (build: Build): string => {
  return formatBuildLinkTextWithTemplate(
    build,
    buildbotGetSettings().getStringSetting('Links.build_link_template'),
  );
};
