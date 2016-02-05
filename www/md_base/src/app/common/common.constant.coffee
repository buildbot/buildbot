invert_constant = (constant_name, inverted_constant_name) ->
    angular.module('common').service inverted_constant_name, [constant_name, (original) ->
        return _.invert(original)
    ]

class Results extends Constant('common')
    constructor: ->
        return {
            SUCCESS: 0
            WARNINGS: 1
            FAILURE: 2
            SKIPPED: 3
            EXCEPTION: 4
            RETRY: 5
            CANCELLED: 6
        }
invert_constant('RESULTS', 'RESULTS_TEXT')
