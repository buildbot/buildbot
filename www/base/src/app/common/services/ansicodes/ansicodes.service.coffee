# simple naive (think wrong) implementation of the spec:
# https://en.wikipedia.org/wiki/ANSI_escape_code

# we only support color modes, and we will just ignore (drop from the log) all others commands

# One \x1b[NNm mode will change the class in the log to ansiNN

# We support concatenated modes change via syntax like \x1b[1;33m
# which is used for 'bright' colors. Previous example, will then convert to class="ansi1 ansi33"

# Nested mode will work, e.g \x1b[1m\x1b[33m is equivalent to \x1b[1;33m.
# \x1b[39m resets the color to default

# This parser does not work across lines
# css class will be reset at each new line

ANSI_RE = /^((\d+)(;\d+)*)?([a-zA-Z])/


class ansicodesService extends Factory('common')
    constructor: ($log) ->
        return {
            parseAnsiSgr: (ansi_entry) ->
                # simple utility to extract ansi sgr (Select Graphic Rendition) codes,
                # and ignore other codes.
                # Invalid codes are restored
                classes = []
                res = ANSI_RE.exec(ansi_entry)
                if res
                    mode = res[4]
                    ansi_entry = ansi_entry.substr(res[0].length)
                    if mode == 'm'
                        classes = res[1]
                        if classes
                            classes = res[1].split(";")
                        else
                            classes = []
                else
                    # illegal code, restore the CSI
                    ansi_entry = '\x1b[' + ansi_entry
                return [ansi_entry, classes]

            ansiSgrToCss: (ansi_classes, css_classes) ->
                if ansi_classes.length == 0
                    return css_classes

                fgbg = {'38': 'fg', '48': 'bg'}
                if fgbg.hasOwnProperty(ansi_classes[0])
                    if ansi_classes.length != 3
                        return {}
                    if ansi_classes[1] == '5'
                        css_classes = { } # (simplification) alway reset color
                        css_classes[fgbg[ansi_classes[0]] + '-' + ansi_classes[2]] = true
                else
                    for i in ansi_classes
                        if i == '39' or i == '0' # "color reset" code and "all attributes off" code
                            css_classes = {}
                        else
                            css_classes[i] = true
                return css_classes

            splitAnsiLine: (line) ->
                html_entries = []
                first_entry = true
                i = 0
                css_classes = {}
                for ansi_entry in line.split(/\x1b\[/)
                    css_class = ""
                    if not first_entry
                        [ansi_entry, ansi_classes] = @parseAnsiSgr(ansi_entry)
                        css_classes = @ansiSgrToCss(ansi_classes, css_classes)
                        css_class = ("ansi" + i for i,v of css_classes).join(' ')
                    if ansi_entry.length > 0
                        html_entries.push(class:css_class, text:_.escape(ansi_entry))
                    first_entry = false
                return html_entries

            ansi2html: (line) ->
                entries = @splitAnsiLine(line)
                html = ""
                for entry in entries
                    html += "<span class='#{entry.class}'>#{entry.text}</span>"
                return html

            injectStyle: ->
                node = document.getElementById("ansicolors")
                if node
                    return
                node = document.createElement('style')
                node.id = "ansicolors"
                node.innerHTML = @generateStyle()
                document.body.appendChild(node)

            generateStyle: ->
                ret = ""
                # first there are the standard 16 colors
                colors = [
                    '000','800','080','880','008','808','088','ccc',
                    '888','f00','0f0','ff0','00f','f0f','0ff','fff'
                ]
                # 6x6x6 color cube encoded in 3 digits hex form
                # note the non-linearity is based on this table
                # http://www.calmar.ws/vim/256-xterm-24bit-rgb-color-chart.html
                clr = ['0', '6', '9', 'a', 'd', 'f']
                for red in [0..5]
                    for green in [0..5]
                        for blue in [0..5]
                            colors.push(clr[red] + clr[green] + clr[blue])
                # greyscale ramp encoded in 6 digits hex form
                for i in [1..24]
                    c = Math.floor(i*256/26).toString(16)
                    if c.length == 1
                        c = "0" + c
                    colors.push(c + c + c)
                for color, i in colors
                    ret += "pre.log .ansifg-#{i} { color: ##{color}; }\n"
                    ret += "pre.log .ansibg-#{i} { background-color: ##{color}; }\n"
                return ret
        }
