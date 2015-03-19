class Home extends Controller
    constructor: ($scope, recentStorage, buildbotService, config, $location) ->
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


        buildbotService.some('builds', order: '-started_at', complete: false).bind($scope, dest_key:'builds_running')
