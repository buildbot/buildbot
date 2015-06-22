class Builds extends Controller
    builders: []

    isHighlighted: (name, param) ->
        return @$state.is(name, param)

    constructor: ($scope, @$state, dataService) ->
        opened = dataService.open()
        opened.closeOnDestroy($scope)
        @builders = opened.getBuilders().getArray()
