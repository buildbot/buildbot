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

import {mergeChunks, parseCssClassesForChunk, parseLogChunk} from "./LogChunkParsing";

describe('LogChunkParsing', () => {
  it('basic', () => {
    const text = "o\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.\n" +
      "o\x1b[32m.\x1b[0m\x1b[31mF\x1b[0m\nh\x1b[32m.\x1b[39m\x1b[32m.\x1b[0m\n";
    const chunk = parseLogChunk(20, text, 's');
    expect(chunk).toEqual({
      firstLine: 20,
      lastLine: 23,
      text: "\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.\n" +
        "\x1b[32m.\x1b[0m\x1b[31mF\x1b[0m\n\x1b[32m.\x1b[39m\x1b[32m.\x1b[0m\n",
      textLineBounds: [0, 56, 77, 99],
      linesWithEscapes: [0, 1, 2],
      lineTypes: "ooh",
      textNoEscapes: null,
      textNoEscapesLineBounds: null,
    });

    const chunkCssClasses = parseCssClassesForChunk(chunk, 20, 23);
    expect(chunkCssClasses).toEqual({
      20: ["DEBUG [plugin]: Loading plugin karma-jasmine.",
        [
          {cssClasses: "ansi36", firstPos: 0, lastPos: 16},
          {cssClasses: "", firstPos: 16, lastPos: 45},
        ],
      ],
      21: [".F",
        [
          {cssClasses: "ansi32", firstPos: 0, lastPos: 1},
          {cssClasses: "ansi31", firstPos: 1, lastPos: 2},
        ],
      ],
      22: ["..",
        [
          {cssClasses: "ansi32", firstPos: 0, lastPos: 1},
          {cssClasses: "ansi32", firstPos: 1, lastPos: 2},
        ],
      ],
    });
  });

  it('basicForceTextNoEscapes', () => {
    const text = "o\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.\n" +
      "o\x1b[32m.\x1b[0m\x1b[31mF\x1b[0m\nh\x1b[32m.\x1b[39m\x1b[32m.\x1b[0m\n";
    const chunk = parseLogChunk(20, text, 's', true);
    expect(chunk).toEqual({
      firstLine: 20,
      lastLine: 23,
      text: "\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.\n" +
        "\x1b[32m.\x1b[0m\x1b[31mF\x1b[0m\n\x1b[32m.\x1b[39m\x1b[32m.\x1b[0m\n",
      textLineBounds: [0, 56, 77, 99],
      linesWithEscapes: null,
      lineTypes: "ooh",
      textNoEscapes: "DEBUG [plugin]: Loading plugin karma-jasmine.\n.F\n..\n",
      textNoEscapesLineBounds: [0, 46, 49]
    });

    const chunkCssClasses = parseCssClassesForChunk(chunk, 20, 23);
    expect(chunkCssClasses).toEqual({
      20: ["DEBUG [plugin]: Loading plugin karma-jasmine.",
        [
          {cssClasses: "ansi36", firstPos: 0, lastPos: 16},
          {cssClasses: "", firstPos: 16, lastPos: 45},
        ],
      ],
      21: [".F",
        [
          {cssClasses: "ansi32", firstPos: 0, lastPos: 1},
          {cssClasses: "ansi31", firstPos: 1, lastPos: 2},
        ],
      ],
      22: ["..",
        [
          {cssClasses: "ansi32", firstPos: 0, lastPos: 1},
          {cssClasses: "ansi32", firstPos: 1, lastPos: 2},
        ],
      ],
    });
  });

  it('mergeNotManyEscapes', () => {
    const text = "o\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.\n" +
      "o\x1b[32m.\x1b[0m\x1b[31mF\x1b[0m\nh\x1b[32m.\x1b[39m\x1b[32m.\x1b[0m\n";
    const chunk1 = parseLogChunk(20, text, 's');
    const chunk2 = parseLogChunk(23, text, 's');
    const mergedChunk = mergeChunks(chunk1, chunk2);
    expect(mergedChunk).toEqual({
      firstLine: 20,
      lastLine: 26,
      text: "\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.\n" +
        "\x1b[32m.\x1b[0m\x1b[31mF\x1b[0m\n\x1b[32m.\x1b[39m\x1b[32m.\x1b[0m\n" +
        "\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.\n" +
        "\x1b[32m.\x1b[0m\x1b[31mF\x1b[0m\n\x1b[32m.\x1b[39m\x1b[32m.\x1b[0m\n",
      textLineBounds: [0, 56, 77, 99, 155, 176, 198],
      linesWithEscapes: [0, 1, 2, 3, 4, 5],
      lineTypes: "oohooh",
      textNoEscapes: null,
      textNoEscapesLineBounds: null,
    });
  })

  it('mergeManyEscapesFirst', () => {
    const text = "o\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.\n" +
      "o\x1b[32m.\x1b[0m\x1b[31mF\x1b[0m\nh\x1b[32m.\x1b[39m\x1b[32m.\x1b[0m\n";
    const chunk1 = parseLogChunk(20, text, 's', true);
    const chunk2 = parseLogChunk(23, text, 's');
    const mergedChunk = mergeChunks(chunk1, chunk2);
    expect(mergedChunk).toEqual({
      firstLine: 20,
      lastLine: 26,
      text: "\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.\n" +
        "\x1b[32m.\x1b[0m\x1b[31mF\x1b[0m\n\x1b[32m.\x1b[39m\x1b[32m.\x1b[0m\n" +
        "\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.\n" +
        "\x1b[32m.\x1b[0m\x1b[31mF\x1b[0m\n\x1b[32m.\x1b[39m\x1b[32m.\x1b[0m\n",
      textLineBounds: [0, 56, 77, 99, 155, 176, 198],
      linesWithEscapes: null,
      lineTypes: "oohooh",
      textNoEscapes: "DEBUG [plugin]: Loading plugin karma-jasmine.\n.F\n..\n" +
        "DEBUG [plugin]: Loading plugin karma-jasmine.\n.F\n..\n",
      textNoEscapesLineBounds: [0, 46, 49, 52, 98, 101],
    });
  })

  it('mergeManyEscapesSecond', () => {
    const text = "o\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.\n" +
      "o\x1b[32m.\x1b[0m\x1b[31mF\x1b[0m\nh\x1b[32m.\x1b[39m\x1b[32m.\x1b[0m\n";
    const chunk1 = parseLogChunk(20, text, 's');
    const chunk2 = parseLogChunk(23, text, 's', true);
    const mergedChunk = mergeChunks(chunk1, chunk2);
    expect(mergedChunk).toEqual({
      firstLine: 20,
      lastLine: 26,
      text: "\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.\n" +
        "\x1b[32m.\x1b[0m\x1b[31mF\x1b[0m\n\x1b[32m.\x1b[39m\x1b[32m.\x1b[0m\n" +
        "\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.\n" +
        "\x1b[32m.\x1b[0m\x1b[31mF\x1b[0m\n\x1b[32m.\x1b[39m\x1b[32m.\x1b[0m\n",
      textLineBounds: [0, 56, 77, 99, 155, 176, 198],
      linesWithEscapes: null,
      lineTypes: "oohooh",
      textNoEscapes: "DEBUG [plugin]: Loading plugin karma-jasmine.\n.F\n..\n" +
        "DEBUG [plugin]: Loading plugin karma-jasmine.\n.F\n..\n",
      textNoEscapesLineBounds: [0, 46, 49, 52, 98, 101],
    });
  })

  it('mergeManyEscapesBoth', () => {
    const text = "o\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.\n" +
      "o\x1b[32m.\x1b[0m\x1b[31mF\x1b[0m\nh\x1b[32m.\x1b[39m\x1b[32m.\x1b[0m\n";
    const chunk1 = parseLogChunk(20, text, 's', true);
    const chunk2 = parseLogChunk(23, text, 's', true);
    const mergedChunk = mergeChunks(chunk1, chunk2);
    expect(mergedChunk).toEqual({
      firstLine: 20,
      lastLine: 26,
      text: "\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.\n" +
        "\x1b[32m.\x1b[0m\x1b[31mF\x1b[0m\n\x1b[32m.\x1b[39m\x1b[32m.\x1b[0m\n" +
        "\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.\n" +
        "\x1b[32m.\x1b[0m\x1b[31mF\x1b[0m\n\x1b[32m.\x1b[39m\x1b[32m.\x1b[0m\n",
      textLineBounds: [0, 56, 77, 99, 155, 176, 198],
      linesWithEscapes: null,
      lineTypes: "oohooh",
      textNoEscapes: "DEBUG [plugin]: Loading plugin karma-jasmine.\n.F\n..\n" +
        "DEBUG [plugin]: Loading plugin karma-jasmine.\n.F\n..\n",
      textNoEscapesLineBounds: [0, 46, 49, 52, 98, 101],
    });
  })
});
