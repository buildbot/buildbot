invert_constant = (constant_name, inverted_constant_name) ->
    angular.module('buildbot.common').service inverted_constant_name, [constant_name, (original) ->
        return _.invert(original)
    ]

angular.module('buildbot.common').constant 'BASEURLAPI', 'api/v2/'
angular.module('buildbot.common').constant 'BASEURLSSE', 'sse/'

angular.module('buildbot.common').constant 'plurals',
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

angular.module('buildbot.common').constant 'results',
    SUCCESS: 0
    WARNINGS: 1
    FAILURE: 2
    SKIPPED: 3
    EXCEPTION: 4
    RETRY: 5
    CANCELLED: 6
invert_constant('results', 'resultsTexts')