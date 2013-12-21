angular.module('app').controller 'builderController',
['$log', '$scope', '$location', 'buildbotService', '$stateParams'
    ($log, $scope, $location, buildbotService, $stateParams) ->
        builder = buildbotService.one('builder', $stateParams.builder)
        builder.bind($scope, 'builder')
        builder.all('forceschedulers').bind($scope, 'forceschedulers')
        builds = builder.all('build')
        buildrequests = builder.all('buildrequest')
        builds.bind($scope, 'builds').then (builds) ->
            watchBuild = (n, i) ->
                builds.one(n).bind($scope.builds, i)
            for i in [0..builds.length - 1]
                b = builds[i]
                if not b.complete
                    watchBuild(b.number, i)
            builds.on "new", (e) ->
                e.msg = JSON.parse(e.data)
                # todo: the new event can call parent's bind event handler after or before
                # so, maybe the new build is at length-1 or will be at length
                i = $scope.builds.length - 1
                if $scope.builds[i].buildid != e.msg.buildid
                    i += 1
                watchBuild(e.msg.number, i)
        buildrequests.bind($scope, 'buildrequests').then (brs) ->
            console.log brs
]
