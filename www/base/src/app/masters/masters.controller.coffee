class Masters extends Controller
    constructor: ($scope, buildbotService) ->
        buildbotService.all('masters').bind($scope)