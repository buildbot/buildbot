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

import {
  LineCssClasses,
  lineContainsEscapeCodes, parseEscapeCodesToClasses, stripLineEscapeCodes
} from "./AnsiEscapeCodes";

export type ParsedLogChunk = {
  firstLine: number;
  lastLine: number;

  // Visible text concatenated into single string (includes escape sequences)
  text: string;

  // An array of numbers specifying the start positions of lines within text. Contains an
  // additional element with value of text.length so that lines can be extracted by
  // taking the following character range: [lineBounds[i], lineBounds[i + 1]).
  textLineBounds: number[];

  // i-th symbol defines the type of i-th line
  lineTypes: string;

  // The indexes of the lines that have one or more escape-sequence character sequences. If null,
  // then the number of lines with escape sequence character sequences is large, and both
  // textNoEscapes and textNoEscapesLineBounds are not null.
  linesWithEscapes: number[]|null;

  // Visible text concatenated into single string (excludes escape sequences). If the value is
  // null, then the number of escape sequences was relatively small, and it was determined to not
  // compute an almost duplicate of text member.
  textNoEscapes: string|null;

  // An array of numbers specifying the start positions of lines within text. Contains an
  // additional element with value of text.length so that lines can be extracted by
  // taking the following character range: [lineBounds[i], lineBounds[i + 1]).
  // If textNoEscapes is null, then this member is null too.
  textNoEscapesLineBounds: number[]|null;
}

export function parseLogChunk(firstLine: number, textWithTypes: string,
                              logType: string): ParsedLogChunk {
  const lines = textWithTypes.split("\n");

  // There is a trailing '\n' that generates an empty line in the end
  if (lines.length > 1) {
    lines.pop();
  }

  let text = '';
  const textLineBounds: number[] = [];
  let linesWithEscapes: number[]|null = [];

  let textNoEscapes: string|null = null;
  let textNoEscapesLineBounds: number[]|null = null;

  let lineTypes = '';

  const logIsStdio = logType === 's';

  let lineIndex = 0;
  for (let line of lines) {
    let lineType = "o";
    if (line.length > 0 && logIsStdio) {
      lineType = line[0];
      line = line.slice(1);
    }

    if (logIsStdio) {
      if (linesWithEscapes === null) {
        // There were so many lines with escape codes that text is converted wholesale
        const noEscapesLine = lineContainsEscapeCodes(line) ? stripLineEscapeCodes(line) : line;
        textNoEscapesLineBounds!.push(textNoEscapes!.length);
        textNoEscapes! += noEscapesLine;
      } else {
        if (lineContainsEscapeCodes(line)) {
          linesWithEscapes.push(lineIndex);
        }

        if (linesWithEscapes.length > 100 && linesWithEscapes.length > lineIndex * 0.3) {
          // Switch between storing indexes of lines with escape sequences to storing whole text
          // with escape sequences removed.
          linesWithEscapes = null;
          textNoEscapesLineBounds = [];
          textNoEscapes = '';
          for (let i = 0; i < lineIndex; ++i) {
            // text contains lines that have already had their lineType symbol removed.
            const iLine = text.slice(textLineBounds[i], textLineBounds[i + 1]);
            const noEscapesLine = lineContainsEscapeCodes(iLine) ? stripLineEscapeCodes(iLine) : iLine;
            textNoEscapesLineBounds.push(textNoEscapes.length);
            textNoEscapes += noEscapesLine;
          }
          // Previous loop excluded the current line, add it too.
          const currNoEscapesLine = lineContainsEscapeCodes(line) ? stripLineEscapeCodes(line) : line;
          textNoEscapesLineBounds.push(textNoEscapes.length);
          textNoEscapes += currNoEscapesLine;
        }
      }
    }

    textLineBounds.push(text.length);
    text += line;
    lineTypes += lineType;
    lineIndex += 1;
  }

  return {
    firstLine: firstLine,
    lastLine: firstLine + lines.length,
    text,
    textLineBounds,
    lineTypes,
    linesWithEscapes,
    textNoEscapes,
    textNoEscapesLineBounds
  };
}

export type ChunkCssClasses = {[globalLine: number]: [string, LineCssClasses[]]};

// Parses ansi escape code information for a span of lines in a particular chunk. Returns a map
// containing key-value pairs, where each key-value pair represents a line with at least on escape
// code. Thee key is line number and value is a tuple containing the line text with escape
// sequences removed and a list of CSS classes to style the line.
export function parseCssClassesForChunk(chunk: ParsedLogChunk,
                                        firstLine: number, lastLine: number) {
  const cssClasses: ChunkCssClasses = {};
  if (firstLine >= chunk.lastLine || lastLine <= chunk.firstLine) {
    return cssClasses;
  }

  if (firstLine < chunk.firstLine) {
    firstLine = chunk.firstLine;
  }
  if (lastLine > chunk.lastLine) {
    lastLine = chunk.lastLine;
  }

  if (chunk.linesWithEscapes !== null) {
    // small number of escaped lines
    const chunkFirstLine = firstLine - chunk.firstLine;
    const chunkLastLine = lastLine - chunk.firstLine;
    for (const chunkLineI of chunk.linesWithEscapes) {
      if (chunkLineI < chunkFirstLine) {
        // It probably makes sense to use binary search in this loop
        continue;
      }
      if (chunkLineI >= chunkLastLine) {
        break;
      }
      // chunkLineI definitely has escape sequences
      const chunkLine = chunk.text.slice(
        chunk.textLineBounds[chunkLineI], chunk.textLineBounds[chunkLineI + 1]);
      const lineI = chunkLineI + chunk.firstLine;

      const [strippedLine, lineCssClasses] = parseEscapeCodesToClasses(chunkLine);
      cssClasses[lineI] = [strippedLine, lineCssClasses!];
    }
  } else {
    // large number of escape sequences
    for (let lineI = firstLine; lineI < lastLine; ++lineI) {
      const chunkLineI = lineI - chunk.firstLine;
      const chunkLine = chunk.text.slice(
        chunk.textLineBounds[chunkLineI], chunk.textLineBounds[chunkLineI + 1]);

      const [strippedLine, lineCssClasses] = parseEscapeCodesToClasses(chunkLine);
      if (lineCssClasses !== null) {
        cssClasses[lineI] = [strippedLine, lineCssClasses!];
      }
    }
  }

  return cssClasses;
}
