class Home extends Controller
    constructor: ($scope, recentStorage, dataService, config, $location) ->
        $scope.baseurl = $location.absUrl().split("#")[0]
        $scope.config = config
        $scope.recent = {}
        recentStorage.getAll().then (e) ->
            $scope.recent.recent_builders = e.recent_builders
            $scope.recent.recent_builds = e.recent_builds
        $scope.clear = ->
            recentStorage.clearAll().then ->
                recentStorage.getAll().then (e) ->
                    $scope.recent.recent_builders = e.recent_builders
                    $scope.recent.recent_builds = e.recent_builds

        data = dataService.open($scope)
        $scope.builds_running = data.getBuilds(order: '-started_at', complete: false).getArray()
