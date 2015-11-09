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
        $scope.recent_builds = data.getBuilds(order: '-buildid', complete: true, limit:20).getArray()
        $scope.builders = data.getBuilders().getArray()
        buildersById = {}
        $scope.hasBuilds = (b) -> b.builds.length > 0
        update_builds = ->
            byNumber = (a, b) -> return a.number - b.number
            $scope.builders.forEach (builder) ->
                builder.builds ?= []
                buildersById[builder.builderid] = builder
            $scope.recent_builds.forEach (build) ->
                builder = buildersById[build.builderid]
                if buildersById[build.builderid].builds.indexOf(build) < 0
                    builder.builds.push(build)
                    builder.builds.sort(byNumber)

        $scope.$watch "recent_builds", update_builds, true # deep watch
        $scope.$watch "builders", update_builds, true # deep watch
