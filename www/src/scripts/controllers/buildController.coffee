angular.module('app').controller 'buildController',
['$log', '$scope', '$location', 'buildbotService', '$stateParams'
    ($log, $scope, $location, buildbotService, $stateParams) ->
        buildbotService.one('builder', $stateParams.builder).get().then (builder) ->
            $scope.builder = builder[0]
        build = buildbotService.one('builder', $stateParams.builder).one('build', $stateParams.build)
        build.all('step').bind($scope, 'steps').then ->
            for step in $scope.steps
                logs = buildbotService.one("step", step.stepid).all("log")
                logs.bind(step, "logs")
        build.bind($scope, 'build').then ->
            buildbotService.one("buildslave", $scope.build.buildslaveid).get().then (buildslave) ->
                $scope.buildslave = buildslave[0]
#            buildbotService.one("buildrequest", $scope.build.buildrequestid).get().then (buildrequest) ->
#                $scope.buildrequest = buildrequest

]
