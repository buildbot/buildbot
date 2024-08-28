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

import {describe, expect, it} from "vitest";
import {computeToggledTag3Way, computeToggledTagOnOff} from "./TagFilterManager";

describe('TagFilterManager', () => {
  describe('computeToggledTag3Way', () => {
    it('empty', () => {
      expect(computeToggledTag3Way([], '')).toEqual([]);
    });

    it('toggle tag when empty', () => {
      expect(computeToggledTag3Way([], 'tag')).toEqual(['+tag']);
      expect(computeToggledTag3Way([], '+tag')).toEqual(['+tag']);
      expect(computeToggledTag3Way([], '-tag')).toEqual(['+tag']);
    });

    it('toggle tag when other tag', () => {
      expect(computeToggledTag3Way(['other'], 'tag')).toEqual(['other', '+tag']);
      expect(computeToggledTag3Way(['other'], '+tag')).toEqual(['other', '+tag']);
      expect(computeToggledTag3Way(['other'], '-tag')).toEqual(['other', '+tag']);
    });

    it('toggle tag when same tag', () => {
      expect(computeToggledTag3Way(['tag'], 'tag')).toEqual([]);
      expect(computeToggledTag3Way(['tag'], '+tag')).toEqual([]);
      expect(computeToggledTag3Way(['tag'], '-tag')).toEqual([]);
      expect(computeToggledTag3Way(['+tag'], 'tag')).toEqual(['-tag']);
      expect(computeToggledTag3Way(['+tag'], '+tag')).toEqual(['-tag']);
      expect(computeToggledTag3Way(['+tag'], '-tag')).toEqual(['-tag']);
      expect(computeToggledTag3Way(['-tag'], 'tag')).toEqual(['tag']);
      expect(computeToggledTag3Way(['-tag'], '+tag')).toEqual(['tag']);
      expect(computeToggledTag3Way(['-tag'], '-tag')).toEqual(['tag']);
    });

    it('toggle tag when same tag and other tag', () => {
      expect(computeToggledTag3Way(['other', 'tag'], 'tag')).toEqual(['other']);
      expect(computeToggledTag3Way(['other', 'tag'], '+tag')).toEqual(['other']);
      expect(computeToggledTag3Way(['other', 'tag'], '-tag')).toEqual(['other']);
      expect(computeToggledTag3Way(['other', '+tag'], 'tag')).toEqual(['other', '-tag']);
      expect(computeToggledTag3Way(['other', '+tag'], '+tag')).toEqual(['other', '-tag']);
      expect(computeToggledTag3Way(['other', '+tag'], '-tag')).toEqual(['other', '-tag']);
      expect(computeToggledTag3Way(['other', '-tag'], 'tag')).toEqual(['other', 'tag']);
      expect(computeToggledTag3Way(['other', '-tag'], '+tag')).toEqual(['other', 'tag']);
      expect(computeToggledTag3Way(['other', '-tag'], '-tag')).toEqual(['other', 'tag']);
    });
  });

  describe('computeToggledTagOnOff', () => {
    it('empty', () => {
      expect(computeToggledTagOnOff([], '')).toEqual([]);
    });

    it('toggle tag when empty', () => {
      expect(computeToggledTagOnOff([], 'tag')).toEqual(['tag']);
    });

    it('toggle tag when other tag', () => {
      expect(computeToggledTagOnOff(['other'], 'tag')).toEqual(['other', 'tag']);
    });

    it('toggle tag when same tag', () => {
      expect(computeToggledTagOnOff(['tag'], 'tag')).toEqual([]);
    });

    it('toggle tag when same tag and other tag', () => {
      expect(computeToggledTagOnOff(['other', 'tag'], 'tag')).toEqual(['other']);
    });
  });
});
