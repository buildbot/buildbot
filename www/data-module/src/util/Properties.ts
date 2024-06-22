/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

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
