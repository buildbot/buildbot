class Home extends Controller
    constructor: ($scope, recentStorage, dataService, config, $location) ->
        $scope.baseurl = $location.absUrl().split("#")[0]
        $scope.config = config

        data = dataService.open().closeOnDestroy($scope)
        $scope.buildsRunning = data.getBuilds(order: '-started_at', complete: false)
        $scope.recentBuilds = data.getBuilds(order: '-buildid', complete: true, limit:20)
        $scope.builders = data.getBuilders()
        $scope.hasBuilds = (b) -> b.builds?.length > 0

        updateBuilds = ->
            byNumber = (a, b) -> return a.number - b.number
            $scope.recentBuilds.forEach (build) ->
                builder = $scope.builders.get(build.builderid)
                if builder?
                    builder.builds ?= []
                    if builder.builds.indexOf(build) < 0
                        builder.builds.push(build)
                        builder.builds.sort(byNumber)

        $scope.recentBuilds.onChange = updateBuilds
        $scope.builders.onChange = updateBuilds
