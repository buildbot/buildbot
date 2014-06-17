angular.module('buildbot.builders').config ['$stateProvider',
    ($stateProvider) ->

        # Name of the state
        name = 'build'

        # Configuration
        cfg =
            tabid: 'builders'
            tabhash: "##{name}"

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/builders/:builder/build/:build'
            data: cfg

        $stateProvider.state(state)
]

angular.module('buildbot.builders').controller 'buildController',
['$log', '$scope', '$location', 'buildbotService', '$stateParams', 'recentStorage'
    ($log, $scope, $location, buildbotService, $stateParams, recentStorage) ->

        buildbotService.bindHierarchy($scope, $stateParams, ['builders', 'builds'])
        .then ([builder, build]) ->
            buildbotService.one("buildslaves", build.buildslaveid).bind($scope)
            buildbotService.one("buildrequests", build.buildrequestid)
            .bind($scope).then (buildrequest) ->
                buildset = buildbotService.one("buildsets", buildrequest.buildsetid)
                buildset.bind($scope)
                buildset.one("properties").bind($scope, dest_key:'properties')
                recentStorage.addBuild
                    link: '#/builders/' + $scope.builder.builderid + '/build/' + $scope.build.buildid
                    caption: $scope.builder.name + ' / ' + $scope.build.buildid

]
