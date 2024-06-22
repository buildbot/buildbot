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

import {repositionPositionedArray} from "./Array";

describe('Array', () => {
  describe('repositionPositionedArray', () => {
    const u = undefined;

    it('no change', () => {
      expect(repositionPositionedArray([1, 2, 3], 0, 0, 3)).toStrictEqual([[1, 2, 3], 0]);
      expect(repositionPositionedArray([1, 2, 3], 2, 2, 5)).toStrictEqual([[1, 2, 3], 2]);
      expect(repositionPositionedArray([1, u, 3, u], 2, 2, 6)).toStrictEqual([[1, u, 3, u], 2]);
    });
    it('new range empty', () => {
      expect(repositionPositionedArray([1, 2, 3], 0, 5, 5)).toStrictEqual([[], 5]);
      expect(repositionPositionedArray([1, 2, 3], 0, 0, 0)).toStrictEqual([[], 0]);
    });
    it('no overlap', () => {
      expect(repositionPositionedArray([1, 2, 3], 10, 2, 5)).toStrictEqual([[u, u, u], 2]);
      expect(repositionPositionedArray([1, 2, 3], 10, 20, 23)).toStrictEqual([[u, u, u], 20]);
    });
    it('reposition', () => {
      expect(repositionPositionedArray([1, 2, 3], 10, 9, 11)).toStrictEqual([[u, 1], 9]);
      expect(repositionPositionedArray([1, 2, 3], 10, 10, 12)).toStrictEqual([[1, 2], 10]);
      expect(repositionPositionedArray([1, 2, 3], 10, 11, 13)).toStrictEqual([[2, 3], 11]);
      expect(repositionPositionedArray([1, 2, 3], 10, 12, 14)).toStrictEqual([[3, u], 12]);

      expect(repositionPositionedArray([1, 2, 3], 10, 8, 11)).toStrictEqual([[u, u, 1], 8]);
      expect(repositionPositionedArray([1, 2, 3], 10, 9, 12)).toStrictEqual([[u, 1, 2], 9]);
      expect(repositionPositionedArray([1, 2, 3], 10, 10, 13)).toStrictEqual([[1, 2, 3], 10]);
      expect(repositionPositionedArray([1, 2, 3], 10, 11, 14)).toStrictEqual([[2, 3, u], 11]);
      expect(repositionPositionedArray([1, 2, 3], 10, 12, 15)).toStrictEqual([[3, u, u], 12]);

      expect(repositionPositionedArray([1, 2, 3], 10, 7, 11)).toStrictEqual([[u, u, u, 1], 7]);
      expect(repositionPositionedArray([1, 2, 3], 10, 8, 12)).toStrictEqual([[u, u, 1, 2], 8]);
      expect(repositionPositionedArray([1, 2, 3], 10, 9, 13)).toStrictEqual([[u, 1, 2, 3], 9]);
      expect(repositionPositionedArray([1, 2, 3], 10, 10, 14)).toStrictEqual([[1, 2, 3, u], 10]);
      expect(repositionPositionedArray([1, 2, 3], 10, 11, 15)).toStrictEqual([[2, 3, u, u], 11]);
      expect(repositionPositionedArray([1, 2, 3], 10, 12, 16)).toStrictEqual([[3, u, u, u], 12]);
    });
  });
});
