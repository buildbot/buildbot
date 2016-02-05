class BuildTab extends Controller
    build: null
    steps: []
    number: ''

    constructor: ($scope, $state, dataService) ->
        data = dataService.open().closeOnDestroy($scope)

        @builderid = parseInt($state.params.builderid)
        @number = parseInt($state.params.number)
        data.getBuilds(builderid:@builderid, number:@number).onNew = (@build) =>
            @steps = @build.loadSteps()
            $scope.builder.selectTab('buildtab', @number)
