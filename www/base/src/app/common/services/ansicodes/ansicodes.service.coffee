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

            splitAnsiLine: (line) ->
                html_entries = []
                first_entry = true
                i = 0
                current_classes = {}
                for ansi_entry in line.split(/\x1b\[/)
                    css_class = ""
                    if not first_entry
                        [ansi_entry, ansi_classes] = @parseAnsiSgr(ansi_entry)
                        for i in ansi_classes
                            if i == '39' # color reset code
                                current_classes = {}
                            else
                                current_classes[i] = true
                        css_class = ("ansi" + i for i,v of current_classes).join(' ')
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
        }
