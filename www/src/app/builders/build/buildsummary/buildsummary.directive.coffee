angular.module('buildbot.builders').directive 'buildsummary',
['$log', 'RecursionHelper',
    ($log, RecursionHelper) ->
        replace: true
        restrict: 'E'
        scope: {buildid:'=', condensed:'='}
        templateUrl: 'views/buildsummary.html'
        compile: RecursionHelper.compile
        controller: 'buildsummaryController'
]