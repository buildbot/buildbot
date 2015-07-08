class Builder extends Controller
    info: {}
    builds: []
    lastBuild: {}

    constructor: ($scope, $state, dataService) ->
        opened = dataService.open()
        opened.closeOnDestroy($scope)

        builderid = $state.params.builderid
        dataService.getBuilders(builderid: builderid).then (data) =>
            if data.length == 0
                alert 'Builder not found!'
                $state.go('builds')
            else
                @info = data[0]
                @builds = dataService.getBuilds(
                    builderid: builderid
                    order: '-buildid'
                    limit: 20
                ).getArray()

        updateLastBuilder = =>
            @lastBuild = @builds[0] if @builds.length

        $scope.$watch 'builder.builds', updateLastBuilder, true
