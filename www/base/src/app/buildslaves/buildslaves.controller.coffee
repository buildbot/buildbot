class Buildslaves extends Controller
    constructor: ($scope, buildbotService) ->
        buildbotService.all('buildslaves').bind($scope)