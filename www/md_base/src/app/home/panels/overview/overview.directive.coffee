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

    workers:
        count: 0
        connections: 0

    builders:
        count: 0

    schedulers:
        count: 0

    constructor: ($scope, dataService) ->
        # TODO: Avoid fetch all the data here after
        # there is a direct API interface
        data = dataService.open().closeOnDestroy($scope)

        data.getMasters().onChange = (masters) =>
            @masters =
                active: 0
                count: masters.length
            for master in masters
                @masters.active++ if master.active

        data.getWorkers().onChange = (workers) =>
            @workers =
                connections: 0
                count: workers.length
            for worker in workers
                @workers.connections += worker.connected_to.length

        data.getBuilders().onChange = (builders) =>
            @builders.count = builders.length

        data.getSchedulers().onChange (schedulers) =>
            @schedulers.count = schedulers.length
