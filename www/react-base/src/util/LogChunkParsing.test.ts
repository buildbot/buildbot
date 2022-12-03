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

import {parseLogChunk} from "./LogChunkParsing";

describe('LogChunkParsing', () => {
  it('basic', () => {
    const text = "o\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.\n" +
      "o\x1b[32m.\x1b[0m\x1b[31mF\x1b[0m\nh\x1b[32m.\x1b[39m\x1b[32m.\x1b[0m\n";
    const ret = parseLogChunk(20, text, 's');
    expect(ret).toEqual({
      firstLine: 20,
      lastLine: 23,
      visibleText: "DEBUG [plugin]: Loading plugin karma-jasmine..F..",
      lineBounds: [0, 45, 47],
      lineTypes: "ooh",
      cssClasses: {
        0: [
          {cssClasses: "ansi36", firstPos: 0, lastPos: 16},
          {cssClasses: "", firstPos: 16, lastPos: 45},
        ],
        1: [
          {cssClasses: "ansi32", firstPos: 0, lastPos: 1},
          {cssClasses: "ansi31", firstPos: 1, lastPos: 2},
        ],
        2: [
          {cssClasses: "ansi32", firstPos: 0, lastPos: 1},
          {cssClasses: "ansi32", firstPos: 1, lastPos: 2},
        ]
      }
    });
  });
});
