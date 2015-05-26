class Overview extends Directive

   constructor: ->
        return {
            restrict: 'E'
            templateUrl: 'views/overview_panel.html'
            controller: '_OverviewController'
            controllerAs: 'overview'
        }

class _Overview extends Controller
    masters:
        count: 0
        active: 0

    slaves:
        count: 0
        connections: 0

    builders:
        count: 0

    schedulers:
        count: 0
 
    constructor: (buildbotService) ->
        buildbotService.all('masters').getList().then (entries) =>
            actives = 0
            for master in entries
                actives += 1 if master.active
            @masters.count = entries.length
            @masters.active = actives
            
        buildbotService.all('buildslaves').getList().then (entries) =>
            connections = 0
            connections += slave.connected_to.length for slave in entries
            @slaves.count = entries.length
            @slaves.connections = connections

        buildbotService.all('builders').getList().then (entries) =>
            @builders.count = entries.length

        buildbotService.all('schedulers').getList().then (entries) =>
            @schedulers.count = entries.length
