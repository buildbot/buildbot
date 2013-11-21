angular.module('app').config [ "$stateProvider", ($stateProvider) ->
    $stateProvider.state "builder.forcebuilder",
        url: "/force/:scheduler",
        onEnter: ["$stateParams", "$state", "$modal", "buildbotService"
            ($stateParams, $state, $modal, buildbotService) ->
                scheduler = buildbotService.one('forceschedulers', $stateParams.scheduler)
                scheduler.get().then (schedulers) ->
                    modal = {}
                    modal.modal = $modal.open
                        templateUrl: "views/forcedialog.html"
                        controller: forceDialogController
                        resolve:
                           scheduler: -> scheduler
                           schedulers: -> schedulers
                           modal: -> modal

                    # We exit the state if the dialog is closed or dismissed
                    goUp = (result) ->
                        $state.go "^"
                    modal.modal.result.then(goUp, goUp)
            ]
    forceDialogController = [ "$scope", "$state", "modal", "scheduler", "schedulers","$rootScope"
        ($scope, $state, modal, scheduler, schedulers, $rootScope) ->
            # prepare default values
            prepareFields = (fields) ->
                for field in fields
                    if field.type == "nested"
                        prepareFields(field.fields)
                    else
                        field.value = field.default
            prepareFields(schedulers[0].all_fields)
            angular.extend $scope,
                rootfield:
                    type: "nested"
                    layout: "simple"
                    fields: schedulers[0].all_fields
                    columns: 1
                sch: schedulers[0]
                ok: ->
                    params = {}
                    fields_ref = {}
                    gatherFields = (fields) ->
                        for field in fields
                            field.errors = ""
                            if field.type == "nested"
                                gatherFields(field.fields)
                            else
                                params[field.fullName] = field.value
                                fields_ref[field.fullName] = field

                    gatherFields(schedulers[0].all_fields)
                    scheduler.control("force", params)
                    .then (res) ->
                        modal.modal.close(res)
                    ,   (err) ->
                        if err.data.error.code == -32602
                            for k, v of err.data.error.message
                                fields_ref[k].errors = v
                        $rootScope.$apply()

                cancel: ->
                    modal.modal.dismiss()
    ]
]
