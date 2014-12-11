class Home extends Controller
    constructor: ($scope, recentStorage, buildbotService) ->
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
