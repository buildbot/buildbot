# simple naive (think wrong) implementation of the spec:
# https://en.wikipedia.org/wiki/ANSI_escape_code
ANSI_RE = /^((\d+)(;\d+)*)?([a-zA-Z])/


class ansicodesService extends Factory('common')
    constructor: ($log) ->
        return {
            parse_ansi_sgr: (ansi_entry) ->
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

            split_ansi_line: (line) ->
                html_entries = []
                console.log line
                first_entry = true
                i = 0
                # should be:
                # this will not work in webkit. \x1b will be returned at the end of each substring,
                # which looks like a bug according to spec
                for ansi_entry in line.split(/\x1b\[/)
                    code = ""
                    if not first_entry
                        [ansi_entry, ansi_classes] = @parse_ansi_sgr(ansi_entry)
                        if ansi_classes
                            code = [("ansi" + i for i in ansi_classes)].join(" ")
                    if ansi_entry.length > 0
                        html_entries.push(class:code, text:_.escape(ansi_entry))
                    first_entry = false
                return html_entries

            ansi2html: (line) ->
                entries = @split_ansi_line(line)
                html = ""
                for entry in entries
                    html += "<span class='#{entry.class}'>#{entry.text}</span>"
                return html
        }
