/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

export function capitalize(s: string) {
  return s[0].toUpperCase() + s.slice(1).toLowerCase();
}

export function copyOrSplit(arrayOrString: any) : string[] {
  if (Array.isArray(arrayOrString)) {
    // return a copy
    return arrayOrString.slice();
  } else if (typeof arrayOrString === 'string') {
    // split the string to get an array
    return arrayOrString.split('/');
  } else {
    throw new TypeError(`Parameter 'arrayOrString' must be a array or a string, not ${typeof arrayOrString}`);
  }
}

export function socketPath(arg: string | string[]) {
  const a = copyOrSplit(arg);
  // if the argument count is even, the last argument is an id
  // Format of properties endpoint is an exception
  // and needs to be properties/*, not properties/*/*
  const stars = ['*'];
  // is it odd?
  if (((a.length % 2) === 1) && (a.at(-1) !== "properties")) {
    stars.push('*');
  }
  return a.concat(stars).join('/');
}

export function socketPathRE(socketPath: string) {
  return new RegExp(`^${socketPath.replace(/\*/g, "[^/]+")}$`);
}

export function restPath(arg: string | string[]) {
  let a = copyOrSplit(arg);
  a = a.filter(e => e !== '*');
  return a.join('/');
}

export function endpointPath(arg: string | string[]) {
  // if the argument count is even, the last argument is an id
  let a = copyOrSplit(arg);
  a = a.filter(e => e !== '*');
  // is it even?
  if ((a.length % 2) === 0) {
    a.pop();
  }
  return a.join('/');
}

export function splitOptions(args: any[]) {
  // keep defined arguments only
  args = args.filter(e => e != null);

  let query = {}; // default
  // get the query parameters
  const last = args[args.length - 1];

  if (typeof last === 'object') {
    query = args.pop();
  }

  return [args, query];
}

export function parse(object : any): any {
  for (const k in object) {
    const v = object[k];
    try {
      object[k] = JSON.parse(v);
    } catch (_error) {}
  } // ignore
  return object;
}

export function numberOrString(str: string | number) : number {
  // if already a number
  if (typeof str === 'number') {
    return str;
  }
  // else parse string to integer
  const number = parseInt(str, 10);
  if (!isNaN(number)) {
    return number;
  } else {
    throw new TypeError(`Can't parse ${str} as number`);
  }
}

export function emailInString(s: string) {
  const emailRegex = /[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*/;
  try {
    return emailRegex.exec(s)?.pop() || '';
  } catch (_error) {
    return '';
  }
}
