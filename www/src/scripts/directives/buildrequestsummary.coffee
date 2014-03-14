angular.module('app').directive 'buildrequestsummary',
['$log', 'RecursionHelper',
    ($log, RecursionHelper) ->
        replace: true
        restrict: 'E'
        scope: {buildrequestid:'='}
        templateUrl: 'views/directives/buildrequestsummary.html'
        compile: RecursionHelper.compile
        controller: 'buildrequestsummaryController'
]

angular.module('app').controller 'buildrequestsummaryController',
['$scope', 'buildbotService', 'findBuilds',
    ($scope, buildbotService, findBuilds) ->

        $scope.$watch "buildrequest.claimed", (n,o) ->
            if n  # if it is unclaimed, then claimed, we need to try again
                findBuilds $scope,
                           $scope.buildrequest.buildrequestid

        buildbotService.one('buildrequests', $scope.buildrequestid)
        .bind($scope)
]
