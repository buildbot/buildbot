angular.module('buildbot.builders').directive 'buildrequestsummary',
['$log', 'RecursionHelper',
    ($log, RecursionHelper) ->
        replace: true
        restrict: 'E'
        scope: {buildrequestid:'='}
        templateUrl: 'views/buildrequestsummary.html'
        compile: RecursionHelper.compile
        controller: 'buildrequestsummaryController'
]
