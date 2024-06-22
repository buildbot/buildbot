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

export const digitCount = (n: number) => {
  return Math.floor(Math.log10(n) + 1);
}

export function alignFloor(n: number, align: number) {
  return Math.floor(n / align) * align;
}

export function alignCeil(n: number, align: number) {
  return Math.ceil(n / align) * align;
}

export function expandRange(start: number, end: number, limitStart: number, limitEnd: number,
                            expand: number): [number, number] {
  start -= expand;
  end += expand;
  return [
    (start < limitStart) ? limitStart : start,
    (end > limitEnd) ? limitEnd : end
  ];
}

export function areRangesOverlapping(startA: number, endA: number, startB: number, endB: number) {
  return (endA > startB && endB > startA);
}

export function isRangeWithinAnother(startIn: number, endIn: number,
                                     startOut: number, endOut: number) {
  return startOut <= startIn && endOut >= endIn;
}

export function limitRangeToSize(start: number, end: number, maxSize: number,
                                 preferredCenter: number): [number, number] {
  if (end - start <= maxSize) {
    return [start, end];
  }
  const byCenterStart = Math.floor(preferredCenter - maxSize / 2);
  const byCenterEnd = byCenterStart + maxSize;
  if (byCenterStart < start) {
    return [start, start + maxSize];
  }
  if (byCenterEnd > end) {
    return [end - maxSize, end];
  }
  return [byCenterStart, byCenterEnd];
}
