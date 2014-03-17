invert_constant = (constant_name, inverted_constant_name) ->
    angular.module('app').service inverted_constant_name, [constant_name, (original) ->
        return _.invert(original)
    ]

angular.module('app').constant 'BASEURLAPI', 'api/v2/'
angular.module('app').constant 'BASEURLSSE', 'sse/'

angular.module('app').constant 'plurals',
    build: "builds"
    builder: "builders"
    buildset: "buildsets"
    buildrequest: "buildrequests"
    buildslave: "buildslaves"
    master: "masters"
    change: "changes"
    step: "steps"
    log: "logs"
    logchunk: "logchunks"
    forcescheduler: "forceschedulers"
    scheduler: "schedulers"
    spec: "specs"
    property: "properties"

invert_constant('plurals', 'singulars')

angular.module('app').constant 'results',
    SUCCESS: 0
    WARNINGS: 1
    FAILURE: 2
    SKIPPED: 3
    EXCEPTION: 4
    RETRY: 5
    CANCELLED: 6
invert_constant('results', 'resultsTexts')
