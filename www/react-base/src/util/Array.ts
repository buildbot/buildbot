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

export function resizeArray<T>(array: T[], size: number, newValue: T) {
  if (array.length > size) {
    array.splice(size);
  } else if (array.length < size) {
    array.push(...Array(size - array.length).fill(newValue));
  }
}

// Given an array + startIndex tuple that represents a space-optimized subarray that stores
// elements in certain index range, repositions the elements into a potentially different index
// range.
export function repositionPositionedArray<T>(array: (T|undefined)[], startIndex: number,
                                             newStartIndex: number,
                                             newEndIndex: number): [(T|undefined)[], number] {
  const endIndex = startIndex + array.length;
  if (startIndex === newStartIndex && endIndex === newEndIndex) {
    return [array, startIndex];
  }

  if (newStartIndex === newEndIndex) {
    return [[], newStartIndex];
  }

  if (newStartIndex >= endIndex || newEndIndex <= newStartIndex) {
    const newArray: (T|undefined)[] = [];
    newArray[newEndIndex - newStartIndex - 1] = undefined; // preallocate
    return [newArray, newStartIndex];
  }

  // Reposition the array
  if (newStartIndex > startIndex) {
    array.splice(0, newStartIndex - startIndex);
  } else if (newStartIndex < startIndex) {
    const newArray: (T|undefined)[] = [];

    newArray[newEndIndex - newStartIndex - 1] = undefined; // preallocate

    const copyCount = Math.min(newEndIndex - newStartIndex, endIndex - startIndex);
    for (let i = 0; i < copyCount; ++i) {
      newArray[startIndex + i - newStartIndex] = array[i];
    }

    array = newArray;
  }

  // Fix array length
  if (array.length > newEndIndex - newStartIndex) {
    array.splice(newEndIndex - newStartIndex);
  } else if (array.length < newEndIndex - newStartIndex) {
    array[newEndIndex - newStartIndex - 1] = undefined; // preallocate
  }

  return [array, newStartIndex];
}
