angular.module 'app', ['restangular', 'ui.bootstrap', 'templates-views', 'ui.router', 'ngAnimate']

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
