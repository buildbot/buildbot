
ANSI_RE = /^((\d+)(;\d+)*)?([a-zA-Z])/

class ansicodesService extends Factory('common')
    constructor: ($log) ->
        console.log "ok"
        return {
            parse_ansi_sgr: (ansi_entry) ->
                # simple utility to extract ansi sgr (Select Graphic Rendition) codes,
                # and ignore other codes.
                # Invalid codes are restored
                classes = []
                res = ANSI_RE.exec(ansi_entry)
                console.log ansi_entry, res
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
        }
