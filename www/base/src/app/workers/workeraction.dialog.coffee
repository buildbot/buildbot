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
                ### @ngInject ###
                onEnter: ($stateParams, $state, $uibModal) ->
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

                    goUp = (result) ->
                        $state.go "^",

                    modal.modal.result.then(goUp, goUp)

class workerActionsDialog extends Controller
    constructor: ($scope, config, $state, modal, workerid, multiple, $rootScope, dataService) ->
        $scope.select_options = []
        $scope.worker_selection = []
        dataService.getWorkers(subscribe: false).onChange = (workers) ->
            if not multiple
                worker = workers.get(workerid)
                $scope.worker_selection.push(worker.name)
            angular.extend $scope,
                multiple: multiple
                worker: worker
                select_options: (worker.name for worker in workers)
                action: (a)->
                    worker.control(a, reason: $scope.reason).then (res) ->
                        modal.modal.close(res.result)
                cancel: ->
                    modal.modal.dismiss()
