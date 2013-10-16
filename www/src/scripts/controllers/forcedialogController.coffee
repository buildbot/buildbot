angular.module('app').config [ "$stateProvider", ($stateProvider) ->
    $stateProvider.state "builder.forcebuilder",
        url: "/force/:scheduler",
        onEnter: ["$stateParams", "$state", "$modal", "buildbotService"
            ($stateParams, $state, $modal, buildbotService) ->
                # FIXME: create a data api to get one forcescheduler by name
                buildbotService.all('forceschedulers').getList().then (schedulers) ->
                    filtered_scheds = []
                    for scheduler in schedulers
                        if scheduler.name == $stateParams.scheduler
                            break
                    modal = {}
                    modal.modal = $modal.open
                        templateUrl: "views/forcedialog.html"
                        controller: ModalInstanceCtrl
                        resolve:
                           scheduler: -> scheduler
                           modal: -> modal

                    modal.modal.result.then (result) ->
                        $state.go "^"
            ]
    ModalInstanceCtrl = [ "$scope", "$state", "modal", "scheduler",
        ($scope, $state, modal, scheduler) ->
            angular.extend $scope,
                sch: scheduler
                ok: ->
                    modal.modal.close()
                cancel: ->
                    modal.modal.close()
    ]
]
