class Workers extends Controller
    constructor: ($scope, dataService, bbSettingsService, resultsService, dataGrouperService, $stateParams, $state, glTopbarContextualActionsService, glBreadcrumbService) ->
        $scope.capitalize = _.capitalize
        _.mixin($scope, resultsService)


        $scope.getUniqueBuilders = (worker) ->
            builders = {}
            masters = {}
            for master in worker.connected_to
                masters[master.masterid] = true
            for buildermaster in worker.configured_on
                if worker.connected_to.length == 0 or masters.hasOwnProperty(buildermaster.masterid)
                    builder = $scope.builders.get(buildermaster.builderid)
                    if builder?
                        builders[buildermaster.builderid] = builder
            return _.values(builders)
        $scope.maybeHideWorker = (worker) ->
            if $stateParams.worker?
                return worker.workerid != +$stateParams.worker
            if $scope.settings.show_old_workers.value
                return worker.configured_on.length == 0
            return 0

        data = dataService.open().closeOnDestroy($scope)

        $scope.builders = data.getBuilders()
        $scope.masters = data.getMasters()
        $scope.workers = data.getWorkers()
        $scope.workers.onChange =  (workers) ->
            breadcrumb = [
                    caption: "Workers"
                    sref: "workers"
            ]
            actions = []
            if $stateParams.worker?
                $scope.worker = worker = workers.get(+$stateParams.worker)

                breadcrumb.push
                    caption: worker.name
                    sref: "worker({worker:#{worker.workerid}})"

                actions.push
                    caption: "Actions..."
                    extra_class: "btn-default"
                    action: ->
                        $state.go("worker.actions")
            else
                actions.push
                    caption: "Actions..."
                    extra_class: "btn-default"
                    action: ->
                        $state.go("workers.actions")
            # reinstall breadcrumb when coming back from forcesched
            setupGl = ->
                glTopbarContextualActionsService.setContextualActions(actions)
                glBreadcrumbService.setBreadcrumb(breadcrumb)
            $scope.$on '$stateChangeSuccess', setupGl
            setupGl()
            $scope.worker_infos = []
            for worker in workers
                worker.num_connections = worker.connected_to.length
                for k, v of worker.workerinfo
                    # we only count workerinfo that is at least defined in one worker
                    if v? and v != "" and $scope.worker_infos.indexOf(k) < 0
                        $scope.worker_infos.push(k)
            $scope.worker_infos.sort()

        byNumber = (a, b) -> return a.number - b.number
        $scope.numbuilds = 200
        if $stateParams.numbuilds?
            $scope.numbuilds = +$stateParams.numbuilds
        if $stateParams.worker?
            $scope.builds = builds = data.getBuilds(
                limit: $scope.numbuilds, workerid: +$stateParams.worker, order: '-started_at')
        else
            builds = data.getBuilds(limit: $scope.numbuilds, order: '-started_at')
        dataGrouperService.groupBy($scope.workers, builds, 'workerid', 'builds')
        $scope.settings = bbSettingsService.getSettingsGroup("Workers")
        $scope.$watch('settings', ->
            bbSettingsService.save()
        , true)
