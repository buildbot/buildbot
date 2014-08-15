class resultsService extends Factory('common')
    constructor: ($log, RESULTS, RESULTS_TEXT) ->
        return {
            results: RESULTS
            resultsTexts: RESULTS_TEXT
            results2class: (build_or_step, pulse) ->
                ret = "results_UNKNOWN"
                if build_or_step?
                    if build_or_step.results? and _.has(RESULTS_TEXT, build_or_step.results)
                        ret = 'results_' + RESULTS_TEXT[build_or_step.results]
                    if (build_or_step.complete == false  && build_or_step.started_at > 0)
                        ret = 'results_PENDING'
                        if pulse?
                            ret += " #{pulse}"
                return ret

            results2text: (build_or_step) ->
                ret = "..."
                if build_or_step?
                    if build_or_step.results? and _.has(RESULTS_TEXT, build_or_step.results)
                        ret = RESULTS_TEXT[build_or_step.results]
                return ret
        }