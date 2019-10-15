/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS205: Consider reworking code to avoid use of IIFEs
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
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

const ANSI_RE = /^((\d+)(;\d+)*)?([a-zA-Z])/;


class ansicodesService {
    constructor($log) {
        return {
            parseAnsiSgr(ansi_entry) {
                // simple utility to extract ansi sgr (Select Graphic Rendition) codes,
                // and ignore other codes.
                // Invalid codes are restored
                let classes = [];
                const res = ANSI_RE.exec(ansi_entry);
                if (res) {
                    const mode = res[4];
                    ansi_entry = ansi_entry.substr(res[0].length);
                    if (mode === 'm') {
                        classes = res[1];
                        if (classes) {
                            classes = res[1].split(";");
                        } else {
                            classes = [];
                        }
                    }
                } else {
                    // illegal code, restore the CSI
                    ansi_entry = `\x1b[${ansi_entry}`;
                }
                return [ansi_entry, classes];
            },

            ansiSgrToCss(ansi_classes, css_classes) {
                if (ansi_classes.length === 0) {
                    return css_classes;
                }

                const fgbg = {'38': 'fg', '48': 'bg'};
                if (fgbg.hasOwnProperty(ansi_classes[0])) {
                    if (ansi_classes.length !== 3) {
                        return {};
                    }
                    if (ansi_classes[1] === '5') {
                        css_classes = { }; // (simplification) always reset color
                        css_classes[fgbg[ansi_classes[0]] + '-' + ansi_classes[2]] = true;
                    }
                } else {
                    for (let i of Array.from(ansi_classes)) {
                        if ((i === '39') || (i === '0')) { // "color reset" code and "all attributes off" code
                            css_classes = {};
                        } else {
                            css_classes[i] = true;
                        }
                    }
                }
                return css_classes;
            },

            splitAnsiLine(line) {
                let i;
                const html_entries = [];
                let first_entry = true;
                i = 0;
                let css_classes = {};
                for (let ansi_entry of Array.from(line.split(/\x1b\[/))) {
                    let css_class = "";
                    if (!first_entry) {
                        let ansi_classes;
                        [ansi_entry, ansi_classes] = Array.from(this.parseAnsiSgr(ansi_entry));
                        css_classes = this.ansiSgrToCss(ansi_classes, css_classes);
                        css_class = ((() => {
                            const result = [];
                            for (i in css_classes) {
                                const v = css_classes[i];
                                result.push(`ansi${i}`);
                            }
                            return result;
                        })()).join(' ');
                    }
                    if (ansi_entry.length > 0) {
                        html_entries.push({class:css_class, text:_.escape(ansi_entry)});
                    }
                    first_entry = false;
                }
                return html_entries;
            },

            ansi2html(line) {
                const entries = this.splitAnsiLine(line);
                let html = "";
                for (let entry of Array.from(entries)) {
                    html += `<span class='${entry.class}'>${entry.text}</span>`;
                }
                return html;
            },

            injectStyle() {
                let node = document.getElementById("ansicolors");
                if (node) {
                    return;
                }
                node = document.createElement('style');
                node.id = "ansicolors";
                node.innerHTML = this.generateStyle();
                document.body.appendChild(node);
            },

            generateStyle() {
                let i;
                let ret = "";
                // first there are the standard 16 colors
                const colors = [
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
                for (i = 1; i <= 24; i++) {
                    let c = Math.floor((i*256)/26).toString(16);
                    if (c.length === 1) {
                        c = `0${c}`;
                    }
                    colors.push(c + c + c);
                }
                for (i = 0; i < colors.length; i++) {
                    const color = colors[i];
                    ret += `pre.log .ansifg-${i} { color: #${color}; }\n`;
                    ret += `pre.log .ansibg-${i} { background-color: #${color}; }\n`;
                }
                return ret;
            }
        };
    }
}


angular.module('common')
.factory('ansicodesService', ['$log', ansicodesService]);
