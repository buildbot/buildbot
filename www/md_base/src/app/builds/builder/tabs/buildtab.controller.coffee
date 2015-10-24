class BuildTab extends Controller
    build: null
    steps: []
    number: ''

    constructor: ($scope, $state, dataService) ->
        data = dataService.open()
        data.closeOnDestroy($scope)

        @builderid = parseInt($state.params.builderid)
        @number = parseInt($state.params.number)
        data.getBuilds(builderid:@builderid, number:@number).then (data) =>
            if data.length < 1
                alert 'No such build found'
            else
                @build = data[0]
                @steps = @build.loadSteps().getArray()
                $scope.builder.selectTab('buildtab', @number)
