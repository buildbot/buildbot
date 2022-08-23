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

const ANSI_RE = new RegExp(/^((\d+)(;\d+)*)?([a-zA-Z])/);


export function parseAnsiSgr(ansiEntry: string): [string, string[]] {
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
    ansiEntry = `\x1b[${ansiEntry}`;
  }
  return [ansiEntry, classes];
}

export function ansiSgrToCss(ansiClasses: string[], cssClasses: {[key: string]: boolean}) {
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
      cssClasses[fgbg[ansiClasses[0]] + '-' + ansiClasses[2]] = true;
    }
  } else {
    for (let i of ansiClasses) {
      if ((i === '39') || (i === '0')) { // "color reset" code and "all attributes off" code
        cssClasses = {};
      } else {
        cssClasses[i] = true;
      }
    }
  }
  return cssClasses;
}

export function splitAnsiLine(line: string) {
  let i;
  const htmlEntries = [];
  let firstEntry = true;
  i = 0;
  let cssClasses: {[key: string]: boolean} = {};
  for (let ansiEntry of line.split(/\x1b\[/)) {
    let css_class = "";
    if (!firstEntry) {
      let ansiClasses: string[];
      [ansiEntry, ansiClasses] = parseAnsiSgr(ansiEntry);
      cssClasses = ansiSgrToCss(ansiClasses, cssClasses);
      css_class = ((() => {
        const result = [];
        for (i in cssClasses) {
          const v = cssClasses[i];
          result.push(`ansi${i}`);
        }
        return result;
      })()).join(' ');
    }
    if (ansiEntry.length > 0) {
      htmlEntries.push({
        class: css_class,
        text: ansiEntry
      });
    }
    firstEntry = false;
  }
  return htmlEntries;
}

export function ansi2html(line: string): JSX.Element[] {
  return splitAnsiLine(line).map((entry, index) => (
    <span key={index} className={entry.class}>{entry.text}</span>
  ));
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
