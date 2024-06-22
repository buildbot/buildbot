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

import {binarySearchGreater, binarySearchGreaterEqual} from "./BinarySearch";

export type LineCssClasses = {
  firstPos: number;
  lastPos: number;
  cssClasses: string;
}

export function cssClassesMapToCssString(classes: {[key: string]: boolean}): string {
  let res = '';
  let isFirst = true;
  for (const c in classes) {
    if (isFirst) {
      isFirst = false;
    } else {
      res += ' ';
    }
    res += c;
  }
  return res;
}

export function combineCssClasses(classesA: string, classesB: string) {
  if (classesA === '')
    return classesB;
  if (classesB === '')
    return classesA;
  return `${classesA} ${classesB}`;
}

function overlaySingleClassesRange(rangeFirstPos: number, rangeLastPos: number,
                                   rangeClasses: string,
                                   overlayFirstPos: number, overlayLastPos: number,
                                   overlayClasses: string) {
  const ret: LineCssClasses[] = [
    {firstPos: overlayFirstPos, lastPos: overlayLastPos,
      cssClasses: combineCssClasses(rangeClasses, overlayClasses)}
  ];

  if (overlayFirstPos > rangeFirstPos) {
    ret.splice(0, 0,
      {firstPos: rangeFirstPos, lastPos: overlayFirstPos, cssClasses: rangeClasses});
  }
  if (overlayLastPos < rangeLastPos) {
    ret.splice(ret.length, 0,
      {firstPos: overlayLastPos, lastPos: rangeLastPos, cssClasses: rangeClasses});
  }
  return ret;
}

export function addOverlayToCssClasses(length: number,
                                       classes: LineCssClasses[]|null,
                                       firstPos: number, lastPos: number,
                                       overlayCssClasses: string): LineCssClasses[] {
  if (firstPos >= length || lastPos > length || firstPos > lastPos) {
    throw Error("Invalid invocation of addOverlayToCssClasses");
  }
  if (classes === null) {
    return overlaySingleClassesRange(0, length, '', firstPos, lastPos, overlayCssClasses);
  }

  const classesCopy = [...classes];

  // It is assumed that classes list covers full range of [0..length). Accordingly it is guaranteed
  // that firstPos and lastPos fall into items in the classes list.
  const firstPosIndex = binarySearchGreater(classes, firstPos, (cl, pos) => cl.lastPos - pos);
  const lastPosIndex = binarySearchGreaterEqual(classes, lastPos, (cl, pos) => cl.lastPos - pos);
  if (firstPosIndex === lastPosIndex) {
    const toReplace = classesCopy[firstPosIndex];
    const replacementClasses = overlaySingleClassesRange(
      toReplace.firstPos, toReplace.lastPos, toReplace.cssClasses,
      firstPos, lastPos, overlayCssClasses);
    classesCopy.splice(firstPosIndex, 1, ...replacementClasses);
    return classesCopy;
  }

  const toReplaceFirst = classesCopy[firstPosIndex];
  const replacementClassesFirst = overlaySingleClassesRange(
    toReplaceFirst.firstPos, toReplaceFirst.lastPos, toReplaceFirst.cssClasses,
    firstPos, toReplaceFirst.lastPos, overlayCssClasses);

  const toReplaceLast = classesCopy[lastPosIndex];
  const replacementClassesLast = overlaySingleClassesRange(
    toReplaceLast.firstPos, toReplaceLast.lastPos, toReplaceLast.cssClasses,
    toReplaceLast.firstPos, lastPos, overlayCssClasses);

  for (let i = firstPosIndex + 1; i < lastPosIndex; ++i) {
    classesCopy[i].cssClasses = combineCssClasses(classesCopy[i].cssClasses, overlayCssClasses);
  }

  // Start with last so that previous indexes aren't invalidated
  classesCopy.splice(lastPosIndex, 1, ...replacementClassesLast);
  classesCopy.splice(firstPosIndex, 1, ...replacementClassesFirst);

  return classesCopy;
}
