class Builds extends Controller
    builders: []

    isHighlighted: (name, param) ->
        return @$state.is(name, param)

    constructor: (@$state, buildbotService) ->
        buildbotService.all('builders').getList().then (builders) =>
            @builders = builders

    
