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

    constructor: ($scope, dataService) ->
        # TODO: Avoid fetch all the data here after
        # there is a direct API interface
        data = dataService.open()
        data.closeOnDestroy($scope)

        data.getMasters().then (masters) =>
            @masters =
                active: 0
                count: masters.length
            for master in masters
                @masters.active++ if master.active

        data.getBuildslaves().then (slaves) =>
            @slaves =
                connections: 0
                count: slaves.length
            for slave in slaves
                @slaves.connections += slave.connected_to.length

        data.getBuilders().then (builders) =>
            @builders.count = builders.length

        data.getSchedulers().then (schedulers) =>
            @schedulers.count = schedulers.length
