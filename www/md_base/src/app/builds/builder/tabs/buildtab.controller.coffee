class BuildTab extends Controller

    constructor: ($scope, $state) ->
        @number = $state.params.number
        $scope.builder.selectTab('buildtab', @number)
    
