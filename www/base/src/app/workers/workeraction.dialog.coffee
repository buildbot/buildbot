class State extends Config
    constructor: ($stateProvider, bbSettingsServiceProvider) ->
        states = [
            name: "worker.actions"
            multiple: false
        ,
            name: "workers.actions"
            multiple: true
        ]
        states.forEach (state) ->
            $stateProvider.state state.name,
                url: "/actions",
                data: group: null
                ### @ngInject ###
                onEnter: ($stateParams, $state, $uibModal, dataService, $q) ->
                    modal = {}
                    modal.modal = $uibModal.open
                        templateUrl: "views/workeractions.html"
                        controller: 'workerActionsDialogController'
                        windowClass: 'modal-xlg'
                        resolve:
                            workerid: -> $stateParams.worker
                            schedulerid: -> $stateParams.scheduler
                            multiple: -> state.multiple
                            modal: -> modal
                            workers: ->
                                d = $q.defer()
                                dataService.getWorkers(subscribe: false).onChange = (workers) ->
                                    workers.then = undefined  # angular will try to call it if it exists
                                    d.resolve(workers)
                                return d.promise

                    goUp = (result) ->
                        $state.go "^",

                    modal.modal.result.then(goUp, goUp)

class workerActionsDialog extends Controller
    constructor: ($scope, config, $state, modal, workerid, multiple, $rootScope, $q, workers) ->
        $scope.select_options = []
        $scope.worker_selection = []
        if not multiple
            worker = workers.get(workerid)
            $scope.worker_selection.push(worker.name)
            $scope.stop_disabled = worker.connected_to.length == 0
            $scope.pause_disabled = worker.paused
            $scope.unpause_disabled = not worker.paused
        else
            $scope.stop_disabled = false
            $scope.pause_disabled = false
            $scope.unpause_disabled = false
        angular.extend $scope,
            multiple: multiple
            worker: worker
            select_options: (w.name for w in workers)
            action: (a)->
                dl = []
                workers.forEach (w) ->
                    if w.name in $scope.worker_selection
                        p = w.control(a, reason: $scope.reason)
                        p.catch (err) ->
                            msg = "unable to #{a} worker #{w.name}:"
                            msg += err.error.message
                            $scope.error = msg
                        dl.push(p)
                $q.all(dl).then (res) ->
                    modal.modal.close(res.result)
            cancel: ->
                modal.modal.dismiss()
