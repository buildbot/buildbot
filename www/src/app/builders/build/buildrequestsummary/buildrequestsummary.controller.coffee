angular.module('buildbot.builders').controller 'buildrequestsummaryController',
    ['$scope', 'buildbotService', 'findBuilds',
        ($scope, buildbotService, findBuilds) ->

            $scope.$watch "buildrequest.claimed", (n,o) ->
                if n  # if it is unclaimed, then claimed, we need to try again
                    findBuilds $scope,
                        $scope.buildrequest.buildrequestid

            buildbotService.one('buildrequests', $scope.buildrequestid)
            .bind($scope)
    ]