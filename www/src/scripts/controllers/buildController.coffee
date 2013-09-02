angular.module('app').controller 'buildController',
['$log', '$scope', '$location', 'buildbotService', '$routeParams'
    ($log, $scope, $location, buildbotService, $routeParams) ->
        buildbotService.one('builder', $routeParams.builder).get().then (builder) ->
            $scope.builder = builder[0]
        build = buildbotService.one('builder', $routeParams.builder).one('build', $routeParams.build)
        build.all('step').bind($scope, 'steps')
        build.bind($scope, 'build').then ->
            buildbotService.one("buildslave", $scope.build.buildslaveid).get().then (buildslave) ->
                $scope.buildslave = buildslave[0]
#            buildbotService.one("buildrequest", $scope.build.buildrequestid).get().then (buildrequest) ->
#                $scope.buildrequest = buildrequest

]
