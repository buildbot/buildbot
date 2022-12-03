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

import {LineCssClasses, parseEscapeCodesToClasses} from "./AnsiEscapeCodes";

export type ParsedLogChunk = {
  firstLine: number;
  lastLine: number;

  // Visible text concatenated into single string
  visibleText: string;

  // An array of numbers precifying the start positions of lines within visibleText. Contains an
  // additional element with value of visibleText.length so that lines can be extracted by
  // taking the following character range: [lineBounds[i], lineBounds[i + 1]).
  lineBounds: number[];

  // i-th symbol defines the type of i-th line
  lineTypes: string;

  // Defines the ansi escape code information for particular line. This is extracted separately
  // as most lines don't have ansi escape codes. The offsets are relative to line start.
  cssClasses: {[line: number]: LineCssClasses[]};
}

export function parseLogChunk(firstLine: number, text: string, logType: string): ParsedLogChunk {
  const lines = text.split("\n");

  // There is a trailing '\n' that generates an empty line in the end
  if (lines.length > 1) {
    lines.pop();
  }

  let visibleText = '';
  const lineBounds: number[] = [];
  let lineTypes = '';
  const ansiCodes: {[line: number]: LineCssClasses[]} = {};

  const logIsStdio = logType === 's';

  let lineIndex = 0;
  for (let line of lines) {
    let lineType = "o";
    if (line.length > 0 && logIsStdio) {
      lineType = line[0];
      line = line.slice(1);
    }

    const [outputLine, lineAnsiCodes] = parseEscapeCodesToClasses(line);
    if (lineAnsiCodes !== null) {
      ansiCodes[lineIndex] = lineAnsiCodes;
    }

    lineBounds.push(visibleText.length);
    visibleText += outputLine;
    lineTypes += lineType;
    lineIndex += 1;
  }

  return {
    firstLine: firstLine,
    lastLine: firstLine + lines.length,
    visibleText,
    lineBounds,
    lineTypes,
    cssClasses: ansiCodes
  };
}
