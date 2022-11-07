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

import {emailInString} from "../data/DataUtils";

export function getPropertyValueArrayOrEmpty(props: {[key: string]: any}, key: string) {
  if (!(key in props)) {
    return [];
  }
  const prop = props[key];
  // each property is an array of two elements: property value and source
  if (!Array.isArray(prop) || prop.length !== 2) {
    return [];
  }
  const value = prop[0];
  if (!Array.isArray(value)) {
    return [];
  }
  return value;
}

export function getPropertyValueOrDefault(props: {[key: string]: any}, key: string, def: any) {
  if (!(key in props)) {
    return def;
  }
  const prop = props[key];
  // each property is an array of two elements: property value and source
  if (!Array.isArray(prop) || prop.length !== 2) {
    return def;
  }
  return prop[0];
}

export function parseChangeAuthorNameAndEmail(author: string): [string, string | null] {
  const email = emailInString(author);
  // Remove email from author string
  if (email) {
    let name: string;
    if (author.split(' ').length > 1) {
      name = author.replace(new RegExp(`\\s<${email}>`), '');
    } else {
      name = email.split("@")[0];
    }
    return [name, email];
  }

  return [author, null];
}
