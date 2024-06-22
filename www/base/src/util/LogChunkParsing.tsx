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
  lineContainsEscapeCodes, parseEscapeCodesToClasses, stripLineEscapeCodes
} from "./AnsiEscapeCodes";
import {LineCssClasses} from "./LineCssClasses";

export type ParsedLogChunk = {
  firstLine: number;
  lastLine: number;

  // Visible text concatenated into single string (includes escape sequences). Each line ends with
  // a newline character, including the last line.
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

  // Visible text concatenated into single string (excludes escape sequences). Each line ends with
  // a newline character, including the last line.
  //
  // If the value is null, then the number of escape sequences was relatively small, and it was
  // determined to not compute an almost duplicate of text member.
  textNoEscapes: string|null;

  // An array of numbers specifying the start positions of lines within textNoEscapes. Contains an
  // additional element with value of textNoEscapes.length so that lines can be extracted by
  // taking the following character range: [lineBounds[i], lineBounds[i + 1]).
  // If textNoEscapes is null, then this member is null too.
  textNoEscapesLineBounds: number[]|null;
}

// Converts the given line-delimited text that includes escape sequences into text that excludes
// escape sequences
function convertTextToNoEscapes(text: string, lineCount: number,
                                textLineBounds: number[]) : [string, number[]]  {
  let textNoEscapes = '';
  let textNoEscapesLineBounds = [];
  for (let i = 0; i < lineCount; ++i) {
    // text contains lines that have already had their lineType symbol removed.
    const iLine = text.slice(textLineBounds[i], textLineBounds[i + 1]);
    const noEscapesLine = lineContainsEscapeCodes(iLine) ? stripLineEscapeCodes(iLine) : iLine;
    textNoEscapesLineBounds.push(textNoEscapes.length);
    textNoEscapes += noEscapesLine;
  }
  return [textNoEscapes, textNoEscapesLineBounds];
}

export function parseLogChunk(firstLine: number, textWithTypes: string, logType: string,
                              forceTextNoEscapes: boolean = false): ParsedLogChunk {
  const lines = textWithTypes.split("\n");

  // There is a trailing '\n' that generates an empty line in the end
  if (lines.length > 1) {
    lines.pop();
  }

  let text = '';
  const textLineBounds: number[] = [0];
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
        textNoEscapes! += noEscapesLine + '\n';
      } else {
        if (lineContainsEscapeCodes(line)) {
          linesWithEscapes.push(lineIndex);
        }

        if (forceTextNoEscapes ||
          (linesWithEscapes.length > 100 && linesWithEscapes.length > lineIndex * 0.3)) {
          // Switch between storing indexes of lines with escape sequences to storing whole text
          // with escape sequences removed.
          linesWithEscapes = null;
          [textNoEscapes, textNoEscapesLineBounds] =
            convertTextToNoEscapes(text, lineIndex, textLineBounds);

          // convertTextToNoEscapes() function above excluded the current line, add it too.
          const currNoEscapesLine = lineContainsEscapeCodes(line) ? stripLineEscapeCodes(line) : line;
          textNoEscapesLineBounds.push(textNoEscapes.length);
          textNoEscapes += currNoEscapesLine + '\n';
        }
      }
    }

    text += line + '\n';
    textLineBounds.push(text.length);
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

export function mergeChunks(chunk1: ParsedLogChunk, chunk2: ParsedLogChunk): ParsedLogChunk {
  if (chunk1.lastLine !== chunk2.firstLine) {
    throw Error("Chunks to be merged must form continuous range");
  }

  const chunk1LineCount = chunk1.lastLine - chunk1.firstLine;
  const chunk2LineCount = chunk2.lastLine - chunk2.firstLine;

  const text = chunk1.text + chunk2.text;
  const textLineBounds =
    [...chunk1.textLineBounds.slice(0, -1), ...chunk2.textLineBounds.map(b => b + chunk1.text.length)];
  const lineTypes = chunk1.lineTypes + chunk2.lineTypes;

  let linesWithEscapes: number[]|null = null;
  let textNoEscapes: string|null = null;
  let textNoEscapesLineBounds: number[]|null = null;
  if (chunk1.linesWithEscapes !== null && chunk2.linesWithEscapes !== null) {
    // both chunks have small number of escaped lines and store escaped line indexes
    linesWithEscapes = [
      ...chunk1.linesWithEscapes,
      ...chunk2.linesWithEscapes.map(l => l + chunk1LineCount)
    ]
  } else {
    // At least one of the chunks has a large number of escaped lines. If one of the chunks doesn't
    // use mode appropriate for many escaped lines, then it is converted to it.
    let chunk1TextNoEscapes: string;
    let chunk1TextNoEscapesLineBounds: number[];
    let chunk2TextNoEscapes: string|null;
    let chunk2TextNoEscapesLineBounds: number[]|null;
    if (chunk1.linesWithEscapes === null) {
      chunk1TextNoEscapes = chunk1.textNoEscapes!;
      chunk1TextNoEscapesLineBounds = chunk1.textNoEscapesLineBounds!;
    } else {
      [chunk1TextNoEscapes, chunk1TextNoEscapesLineBounds] =
        convertTextToNoEscapes(chunk1.text, chunk1LineCount, chunk1.textLineBounds);
    }
    if (chunk2.linesWithEscapes === null) {
      chunk2TextNoEscapes = chunk2.textNoEscapes!;
      chunk2TextNoEscapesLineBounds = chunk2.textNoEscapesLineBounds!;
    } else {
      [chunk2TextNoEscapes, chunk2TextNoEscapesLineBounds] =
        convertTextToNoEscapes(chunk2.text, chunk2LineCount, chunk2.textLineBounds);
    }

    textNoEscapes = chunk1TextNoEscapes + chunk2TextNoEscapes!;
    textNoEscapesLineBounds = [
      ...chunk1TextNoEscapesLineBounds,
      ...chunk2TextNoEscapesLineBounds.map(b => b + chunk1TextNoEscapes.length)
    ]
  }

  return {
    firstLine: chunk1.firstLine,
    lastLine: chunk2.lastLine,
    text,
    textLineBounds,
    lineTypes,
    linesWithEscapes,
    textNoEscapes,
    textNoEscapesLineBounds
  }
}

export type ChunkCssClasses = {[globalLine: number]: [string, LineCssClasses[]]};

// Parses ansi escape code information for a span of lines in a particular chunk. Returns a map
// containing key-value pairs, where each key-value pair represents a line with at least on escape
// code. The key is line number and value is a tuple containing the line text with escape
// sequences removed and a list of CSS classes to style the line. The line text and the
// text positions in the list exclude any trailing newlines.
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
        chunk.textLineBounds[chunkLineI], chunk.textLineBounds[chunkLineI + 1] - 1);
      const lineI = chunkLineI + chunk.firstLine;

      const [strippedLine, lineCssClasses] = parseEscapeCodesToClasses(chunkLine);
      cssClasses[lineI] = [strippedLine, lineCssClasses!];
    }
  } else {
    // large number of escape sequences
    for (let lineI = firstLine; lineI < lastLine; ++lineI) {
      const chunkLineI = lineI - chunk.firstLine;
      const chunkLine = chunk.text.slice(
        chunk.textLineBounds[chunkLineI], chunk.textLineBounds[chunkLineI + 1] - 1);

      const [strippedLine, lineCssClasses] = parseEscapeCodesToClasses(chunkLine);
      if (lineCssClasses !== null) {
        cssClasses[lineI] = [strippedLine, lineCssClasses!];
      }
    }
  }

  return cssClasses;
}
