angular.module('buildbot.builders').config ['$stateProvider',
    ($stateProvider) ->

        # Name of the state
        name = 'buildrequest'

        # Configuration
        cfg =
            tabid: 'builders'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/buildrequests/:buildrequest?redirect_to_build'
            data: cfg

        $stateProvider.state(state)
]

angular.module('buildbot.builders').controller 'buildrequestController',
['$scope', 'buildbotService', '$stateParams', 'findBuilds',
    ($scope, buildbotService, $stateParams, findBuilds) ->

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
