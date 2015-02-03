class Buildslaves extends Controller
    constructor: ($scope, buildbotService) ->
        buildbotService.all('buildslaves').bind $scope,
            onchild: (slave) ->
                console.log slave
                slave.builders = []
                slave.configured_on.forEach (c) ->
                    buildbotService.one('builders', c.builderid).get().then (b) ->
                        slave.builders.push(b)
