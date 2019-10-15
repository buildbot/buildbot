/*
 * decaffeinate suggestions:
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class resultsService {
    constructor($log, RESULTS, RESULTS_TEXT) {
        return {
            results: RESULTS,
            resultsTexts: RESULTS_TEXT,
            results2class(build_or_step, pulse) {
                let ret = "results_UNKNOWN";
                if (build_or_step != null) {
                    if ((build_or_step.results != null) && _.has(RESULTS_TEXT, build_or_step.results)) {
                        ret = `results_${RESULTS_TEXT[build_or_step.results]}`;
                    }
                    if ((build_or_step.complete === false)  && (build_or_step.started_at > 0)) {
                        ret = 'results_PENDING';
                        if (pulse != null) {
                            ret += ` ${pulse}`;
                        }
                    }
                }
                return ret;
            },

            results2text(build_or_step) {
                let ret = "...";
                if (build_or_step != null) {
                    if ((build_or_step.results != null) && _.has(RESULTS_TEXT, build_or_step.results)) {
                        ret = RESULTS_TEXT[build_or_step.results];
                    }
                }
                return ret;
            }
        };
    }
}


angular.module('common')
.factory('resultsService', ['$log', 'RESULTS', 'RESULTS_TEXT', resultsService]);
