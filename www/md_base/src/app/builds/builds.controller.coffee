class Builds extends Controller
    builders: []
    constructor: (buildbotService) ->
        buildbotService.all('builders').getList().then (builders) =>
            @builders = builders

    
