class BuildTab extends Controller
    build: {}
    number: ''

    constructor: ($scope, $state, dataService) ->
        opened = dataService.open()
        opened.closeOnDestroy($scope)

        @builderid = $state.params.builderid
        @number = $state.params.number
        opened.getBuilds(builderid:@builderid, number:@number).then (data) =>
            if data.length < 1
                alert 'No such build found'
            else
                @build = data[0]
                $scope.builder.selectTab('buildtab', @number)
