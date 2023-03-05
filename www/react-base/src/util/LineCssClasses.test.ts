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

import {addOverlayToCssClasses} from "./LineCssClasses";

describe('LineCssClasses', () => {
  describe('addOverlayToCssClasses', () => {
    it('throws error invalid positions', () => {
      expect(() => addOverlayToCssClasses(10, null, 11, 12, 'abc')).toThrowError();
      expect(() => addOverlayToCssClasses(10, null, 9, 12, 'abc')).toThrowError();
      expect(() => addOverlayToCssClasses(10, null, 8, 6, 'abc')).toThrowError();
    });
    it('no classes', () => {
      expect(addOverlayToCssClasses(10, null, 0, 5, 'abc')).toEqual([
        {firstPos: 0, lastPos: 5, cssClasses: 'abc'},
        {firstPos: 5, lastPos: 10, cssClasses: ''},
      ]);
      expect(addOverlayToCssClasses(10, null, 5, 10, 'abc')).toEqual([
        {firstPos: 0, lastPos: 5, cssClasses: ''},
        {firstPos: 5, lastPos: 10, cssClasses: 'abc'},
      ]);
      expect(addOverlayToCssClasses(10, null, 0, 10, 'abc')).toEqual([
        {firstPos: 0, lastPos: 10, cssClasses: 'abc'},
      ]);
    });
    it('overlays single classes subrange (first)', () => {
      expect(addOverlayToCssClasses(10, [
        {firstPos: 0, lastPos: 5, cssClasses: '1'},
        {firstPos: 5, lastPos: 10, cssClasses: '2'},
      ], 0, 5, 'abc')).toEqual([
        {firstPos: 0, lastPos: 5, cssClasses: '1 abc'},
        {firstPos: 5, lastPos: 10, cssClasses: '2'},
      ]);
      expect(addOverlayToCssClasses(10, [
        {firstPos: 0, lastPos: 5, cssClasses: '1'},
        {firstPos: 5, lastPos: 10, cssClasses: '2'},
      ], 0, 2, 'abc')).toEqual([
        {firstPos: 0, lastPos: 2, cssClasses: '1 abc'},
        {firstPos: 2, lastPos: 5, cssClasses: '1'},
        {firstPos: 5, lastPos: 10, cssClasses: '2'},
      ]);
      expect(addOverlayToCssClasses(10, [
        {firstPos: 0, lastPos: 5, cssClasses: '1'},
        {firstPos: 5, lastPos: 10, cssClasses: '2'},
      ], 2, 5, 'abc')).toEqual([
        {firstPos: 0, lastPos: 2, cssClasses: '1'},
        {firstPos: 2, lastPos: 5, cssClasses: '1 abc'},
        {firstPos: 5, lastPos: 10, cssClasses: '2'},
      ]);
    });
    it('overlays single classes subrange (last)', () => {
      expect(addOverlayToCssClasses(10, [
        {firstPos: 0, lastPos: 5, cssClasses: '1'},
        {firstPos: 5, lastPos: 10, cssClasses: '2'},
      ], 5, 10, 'abc')).toEqual([
        {firstPos: 0, lastPos: 5, cssClasses: '1'},
        {firstPos: 5, lastPos: 10, cssClasses: '2 abc'},
      ]);
      expect(addOverlayToCssClasses(10, [
        {firstPos: 0, lastPos: 5, cssClasses: '1'},
        {firstPos: 5, lastPos: 10, cssClasses: '2'},
      ], 5, 7, 'abc')).toEqual([
        {firstPos: 0, lastPos: 5, cssClasses: '1'},
        {firstPos: 5, lastPos: 7, cssClasses: '2 abc'},
        {firstPos: 7, lastPos: 10, cssClasses: '2'},
      ]);
      expect(addOverlayToCssClasses(10, [
        {firstPos: 0, lastPos: 5, cssClasses: '1'},
        {firstPos: 5, lastPos: 10, cssClasses: '2'},
      ], 7, 10, 'abc')).toEqual([
        {firstPos: 0, lastPos: 5, cssClasses: '1'},
        {firstPos: 5, lastPos: 7, cssClasses: '2'},
        {firstPos: 7, lastPos: 10, cssClasses: '2 abc'},
      ]);
    });
    it('overlays two classes subranges', () => {
      expect(addOverlayToCssClasses(15, [
        {firstPos: 0, lastPos: 5, cssClasses: '1'},
        {firstPos: 5, lastPos: 10, cssClasses: '2'},
        {firstPos: 10, lastPos: 15, cssClasses: '3'},
      ], 5, 15, 'abc')).toEqual([
        {firstPos: 0, lastPos: 5, cssClasses: '1'},
        {firstPos: 5, lastPos: 10, cssClasses: '2 abc'},
        {firstPos: 10, lastPos: 15, cssClasses: '3 abc'},
      ]);
      expect(addOverlayToCssClasses(15, [
        {firstPos: 0, lastPos: 5, cssClasses: '1'},
        {firstPos: 5, lastPos: 10, cssClasses: '2'},
        {firstPos: 10, lastPos: 15, cssClasses: '3'},
      ], 5, 12, 'abc')).toEqual([
        {firstPos: 0, lastPos: 5, cssClasses: '1'},
        {firstPos: 5, lastPos: 10, cssClasses: '2 abc'},
        {firstPos: 10, lastPos: 12, cssClasses: '3 abc'},
        {firstPos: 12, lastPos: 15, cssClasses: '3'},
      ]);
      expect(addOverlayToCssClasses(15, [
        {firstPos: 0, lastPos: 5, cssClasses: '1'},
        {firstPos: 5, lastPos: 10, cssClasses: '2'},
        {firstPos: 10, lastPos: 15, cssClasses: '3'},
      ], 7, 15, 'abc')).toEqual([
        {firstPos: 0, lastPos: 5, cssClasses: '1'},
        {firstPos: 5, lastPos: 7, cssClasses: '2'},
        {firstPos: 7, lastPos: 10, cssClasses: '2 abc'},
        {firstPos: 10, lastPos: 15, cssClasses: '3 abc'},
      ]);
      expect(addOverlayToCssClasses(15, [
        {firstPos: 0, lastPos: 5, cssClasses: '1'},
        {firstPos: 5, lastPos: 10, cssClasses: '2'},
        {firstPos: 10, lastPos: 15, cssClasses: '3'},
      ], 7, 12, 'abc')).toEqual([
        {firstPos: 0, lastPos: 5, cssClasses: '1'},
        {firstPos: 5, lastPos: 7, cssClasses: '2'},
        {firstPos: 7, lastPos: 10, cssClasses: '2 abc'},
        {firstPos: 10, lastPos: 12, cssClasses: '3 abc'},
        {firstPos: 12, lastPos: 15, cssClasses: '3'},
      ]);
    });
    it('overlays three classes subranges', () => {
      expect(addOverlayToCssClasses(15, [
        {firstPos: 0, lastPos: 5, cssClasses: '1'},
        {firstPos: 5, lastPos: 10, cssClasses: '2'},
        {firstPos: 10, lastPos: 15, cssClasses: '3'},
      ], 0, 15, 'abc')).toEqual([
        {firstPos: 0, lastPos: 5, cssClasses: '1 abc'},
        {firstPos: 5, lastPos: 10, cssClasses: '2 abc'},
        {firstPos: 10, lastPos: 15, cssClasses: '3 abc'},
      ]);
      expect(addOverlayToCssClasses(15, [
        {firstPos: 0, lastPos: 5, cssClasses: '1'},
        {firstPos: 5, lastPos: 10, cssClasses: '2'},
        {firstPos: 10, lastPos: 15, cssClasses: '3'},
      ], 0, 12, 'abc')).toEqual([
        {firstPos: 0, lastPos: 5, cssClasses: '1 abc'},
        {firstPos: 5, lastPos: 10, cssClasses: '2 abc'},
        {firstPos: 10, lastPos: 12, cssClasses: '3 abc'},
        {firstPos: 12, lastPos: 15, cssClasses: '3'},
      ]);
      expect(addOverlayToCssClasses(15, [
        {firstPos: 0, lastPos: 5, cssClasses: '1'},
        {firstPos: 5, lastPos: 10, cssClasses: '2'},
        {firstPos: 10, lastPos: 15, cssClasses: '3'},
      ], 2, 15, 'abc')).toEqual([
        {firstPos: 0, lastPos: 2, cssClasses: '1'},
        {firstPos: 2, lastPos: 5, cssClasses: '1 abc'},
        {firstPos: 5, lastPos: 10, cssClasses: '2 abc'},
        {firstPos: 10, lastPos: 15, cssClasses: '3 abc'},
      ]);
      expect(addOverlayToCssClasses(15, [
        {firstPos: 0, lastPos: 5, cssClasses: '1'},
        {firstPos: 5, lastPos: 10, cssClasses: '2'},
        {firstPos: 10, lastPos: 15, cssClasses: '3'},
      ], 2, 12, 'abc')).toEqual([
        {firstPos: 0, lastPos: 2, cssClasses: '1'},
        {firstPos: 2, lastPos: 5, cssClasses: '1 abc'},
        {firstPos: 5, lastPos: 10, cssClasses: '2 abc'},
        {firstPos: 10, lastPos: 12, cssClasses: '3 abc'},
        {firstPos: 12, lastPos: 15, cssClasses: '3'},
      ]);
    });
  });
});
