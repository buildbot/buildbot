angular.module('buildbot.builders').factory 'resultsService',
['$log', 'results', 'resultsTexts'
    ($log, results, resultsTexts) ->
        results: results
        resultsTexts: resultsTexts
        results2class: (build_or_step, pulse) ->
            ret = "results_UNKNOWN"
            if build_or_step?
                if build_or_step.results? and _.has(resultsTexts, build_or_step.results)
                    ret = 'results_' + resultsTexts[build_or_step.results]
                if (build_or_step.complete == false  && build_or_step.started_at > 0)
                    ret = 'results_PENDING'
                    if pulse?
                        ret += " #{pulse}"
            return ret

        results2text: (build_or_step) ->
            ret = "..."
            if build_or_step?
                if build_or_step.results? and _.has(resultsTexts, build_or_step.results)
                    ret = resultsTexts[build_or_step.results]
            return ret
]
