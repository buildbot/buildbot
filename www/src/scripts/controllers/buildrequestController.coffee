angular.module('app').controller 'buildrequestController',
['$log', '$scope', '$location', 'buildbotService', '$stateParams', 'findBuilds',
    ($log, $scope, $location, buildbotService, $stateParams, findBuilds) ->

        $scope.$watch "buildrequest.claimed", (n,o) ->
            if n  # if it is unclaimed, then claimed, we need to try again
                findBuilds $scope,
                           $scope.buildrequest.buildrequestid,
                           $stateParams.redirect_to_build

        buildbotService.bindHierarchy($scope, $stateParams, ['buildrequests'])
        .then ([buildrequest]) ->
            buildbotService.one("buildsets", buildrequest.buildsetid)
            .bind($scope)

]
