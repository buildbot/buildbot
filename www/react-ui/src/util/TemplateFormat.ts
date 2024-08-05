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

export type ParsedTemplate = {
  template: string;
  replacements: Set<string>;
  errors: string[]
}

export function parseTemplate(template: string) : ParsedTemplate {
  const replacements = new Set<string>();
  const errors: string[] = [];

  let i = template.indexOf("%(");
  while (i >= 0) {
    let iend = template.indexOf(")", i + 2);
    if (iend < 0) {
      errors.push(`Unclosed replacement field at position ${i}`);
      break;
    }
    if (i + 2 === iend) {
      errors.push(`Empty replacement at position ${i}`);
      break;
    }
    replacements.add(template.substring(i + 2, iend));
    i = template.indexOf("%(", iend + 1);
  }
  return {
    template: template,
    replacements: replacements,
    errors: errors
  }
}

export function fillTemplate(template: string, replacements: Map<string, string>) {
  let result = '';
  let i = template.indexOf("%(");
  if (i >= 0) {
    result += template.substring(0, i);
  } else {
    result += template;
  }

  while (i >= 0) {
    let iend = template.indexOf(")", i + 2);
    if (iend < 0) {
      return result;
    }
    if (i + 2 === iend) {
      return result;
    }
    const key = template.substring(i + 2, iend);
    result += replacements.get(key) ?? '';
    i = template.indexOf("%(", iend + 1);
    if (i >= 0) {
      result += template.substring(iend + 1, i);
    } else {
      result += template.substring(iend + 1);
    }
  }
  return result;
}
