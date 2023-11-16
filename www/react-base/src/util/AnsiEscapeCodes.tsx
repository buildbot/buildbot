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

// simple naive (think wrong) implementation of the spec:
// https://en.wikipedia.org/wiki/ANSI_escape_code

// we only support color modes, and we will just ignore (drop from the log) all others commands

// One \x1b[NNm mode will change the class in the log to ansiNN

// We support concatenated modes change via syntax like \x1b[1;33m
// which is used for 'bright' colors. Previous example, will then convert to class="ansi1 ansi33"

// Nested mode will work, e.g \x1b[1m\x1b[33m is equivalent to \x1b[1;33m.
// \x1b[39m resets the color to default

// This parser does not work across lines
// css class will be reset at each new line

import {cssClassesMapToCssString, LineCssClasses} from "./LineCssClasses";

const ANSI_RE = new RegExp(/^((\d+)(;\d+)*)?([a-zA-Z])/);
const CSI_PREFIX = "\x1b[";

export function parseAnsiSgrEntry(ansiEntry: string): [string, string[]] {
  // simple utility to extract ansi sgr (Select Graphic Rendition) codes,
  // and ignore other codes.
  // Invalid codes are restored
  let classes: string[] = [];
  const res = ANSI_RE.exec(ansiEntry);
  if (res) {
    const mode = res[4];
    ansiEntry = ansiEntry.substr(res[0].length);
    if (mode === 'm') {
      if (res[1]) {
        classes = res[1].split(";");
      } else {
        classes = [];
      }
    }
  } else {
    // illegal code, restore the CSI
    ansiEntry = CSI_PREFIX + ansiEntry;
  }
  return [ansiEntry, classes];
}

export function stripAnsiSgrEntry(ansiEntry: string): string {
  // simple utility to strip ansi sgr (Select Graphic Rendition) codes,
  // and ignore other codes.
  // Invalid codes are restored
  const res = ANSI_RE.exec(ansiEntry);
  if (res) {
    ansiEntry = ansiEntry.substr(res[0].length);
  } else {
    // illegal code, restore the CSI
    ansiEntry = CSI_PREFIX + ansiEntry;
  }
  return ansiEntry;
}

export function ansiSgrClassesToCss(ansiClasses: string[], cssClasses: {[key: string]: boolean}) {
  if (ansiClasses.length === 0) {
    return cssClasses;
  }

  const fgbg: {[key: string]: string} = {'38': 'fg', '48': 'bg'};
  if (ansiClasses[0] in fgbg) {
    if (ansiClasses.length !== 3) {
      return {};
    }
    if (ansiClasses[1] === '5') {
      cssClasses = { }; // (simplification) always reset color
      cssClasses[`ansi${fgbg[ansiClasses[0]]}-${ansiClasses[2]}`] = true;
    }
  } else {
    for (let i of ansiClasses) {
      if ((i === '39') || (i === '0')) { // "color reset" code and "all attributes off" code
        cssClasses = {};
      } else {
        cssClasses[`ansi${i}`] = true;
      }
    }
  }
  return cssClasses;
}

export function lineContainsEscapeCodes(line: string) {
  return line.includes(CSI_PREFIX);
}

export function stripLineEscapeCodes(line: string) {
  let firstEntry = true;
  let outputText = "";

  for (const ansiEntry of line.split(CSI_PREFIX)) {
    let entryOutputText: string;
    if (firstEntry) {
      entryOutputText = ansiEntry;
      firstEntry = false;
    } else {
      entryOutputText = stripAnsiSgrEntry(ansiEntry);
    }
    if (entryOutputText.length > 0) {
      outputText += entryOutputText;
    }
  }

  return outputText;
}

export function parseEscapeCodesToClasses(line: string): [string, LineCssClasses[] | null] {
  if (!lineContainsEscapeCodes(line)) {
    return [line, null];
  }

  let firstEntry = true;
  let outputText = "";
  const outputClasses: LineCssClasses[] = [];
  let cssClassesMap: {[key: string]: boolean} = {};

  for (const ansiEntry of line.split(CSI_PREFIX)) {
    let entryOutputText: string;
    let cssClasses : string;
    if (firstEntry) {
      entryOutputText = ansiEntry;
      cssClasses = '';
      firstEntry = false;
    } else {
      let ansiClasses: string[];
      [entryOutputText, ansiClasses] = parseAnsiSgrEntry(ansiEntry);
      cssClassesMap = ansiSgrClassesToCss(ansiClasses, cssClassesMap);
      cssClasses = cssClassesMapToCssString(cssClassesMap);
    }
    if (entryOutputText.length > 0) {
      outputClasses.push({
        firstPos: outputText.length,
        lastPos: outputText.length + entryOutputText.length,
        cssClasses
      })
      outputText += entryOutputText;
    }
  }

  return [outputText, outputClasses];
}

// Converts line information to TSX elements. Line information is supplied either as a substring
// (text from lineStart inclusive to lineEnd exclusive) in case it does not contain escape
// sequences, or a parsed line with CSS class information.
//
// Both line substring and the parsed line information must exclude trailing newline character.
export function escapeClassesToHtml(text: string, lineStart: number, lineEnd: number,
                                    cssClassesWithText: [string | null, LineCssClasses[] | null] | undefined) {
  if (cssClassesWithText === undefined || cssClassesWithText[1] === null ||
      cssClassesWithText[1].length === 0) {
    return [
      <span key={1}>{text.slice(lineStart, lineEnd)}</span>
    ]
  }

  const [lineText, cssClasses] = cssClassesWithText;
  return cssClasses.map((cssClass, index) => {
    // Note that outputText already refers to the line text
    const classText = lineText === null
      ? text.slice(lineStart + cssClass.firstPos, lineStart + cssClass.lastPos)
      : lineText.slice(cssClass.firstPos, cssClass.lastPos);
    return (
      <span key={index} className={cssClass.cssClasses}>{classText}</span>
    );
  });
}

// Parses escape codes in the given line and converts it TSX elements. The input line must exclude
// trailing newline character.
export function ansi2html(line: string): JSX.Element[] {
  const [text, cssClasses] = parseEscapeCodesToClasses(line);
  return escapeClassesToHtml(text, 0, text.length, [text, cssClasses]);
}

export function generateStyle(cssSelector: string) {
  let i;
  let ret = "";
  // first there are the standard 16 colors
  const colors: string[] = [
    '000','800','080','880','008','808','088','ccc',
    '888','f00','0f0','ff0','00f','f0f','0ff','fff'
  ];
  // 6x6x6 color cube encoded in 3 digits hex form
  // note the non-linearity is based on this table
  // http://www.calmar.ws/vim/256-xterm-24bit-rgb-color-chart.html
  const clr = ['0', '6', '9', 'a', 'd', 'f'];
  for (let red = 0; red <= 5; red++) {
    for (let green = 0; green <= 5; green++) {
      for (let blue = 0; blue <= 5; blue++) {
        colors.push(clr[red] + clr[green] + clr[blue]);
      }
    }
  }
  // greyscale ramp encoded in 6 digits hex form
  for (let i = 1; i <= 24; i++) {
    let c = Math.floor((i*256)/26).toString(16);
    if (c.length === 1) {
      c = `0${c}`;
    }
    colors.push(c + c + c);
  }
  for (i = 0; i < colors.length; i++) {
    const color = colors[i];
    ret += `${cssSelector} .ansifg-${i} { color: #${color}; }\n`;
    ret += `${cssSelector} .ansibg-${i} { background-color: #${color}; }\n`;
  }
  return ret;
}

export function generateStyleElement(cssSelector: string): JSX.Element {
  return <style>{generateStyle(cssSelector)}</style>
}
