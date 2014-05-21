angular.module('app').config [ "$stateProvider", ($stateProvider) ->
    $stateProvider.state "builder.forcebuilder",
        url: "/force/:scheduler",
        onEnter: ["$stateParams", "$state", "$modal", "buildbotService"
            ($stateParams, $state, $modal, buildbotService) ->
                scheduler = buildbotService.one('forceschedulers', $stateParams.scheduler)
                scheduler.get().then (scheduler_data) ->
                    modal = {}
                    modal.modal = $modal.open
                        templateUrl: "views/forcedialog.html"
                        controller: forceDialogController
                        resolve:
                            builderid: -> $stateParams.builder
                            scheduler: -> scheduler
                            scheduler_data: -> scheduler_data
                            modal: -> modal

                    # We exit the state if the dialog is closed or dismissed
                    goBuild = (result) ->
                        [ buildsetid, brids ] = result
                        buildernames = _.keys(brids)
                        if buildernames.length == 1
                            $state.go "buildrequest",
                                buildrequest: brids[buildernames[0]]
                                redirect_to_build: true
                    goUp = (result) ->
                        $state.go "^",

                    modal.modal.result.then(goBuild, goUp)
            ]
    forceDialogController = [ "$scope", "$state", "modal", "scheduler",
        "scheduler_data","$rootScope", "builderid"
        ($scope, $state, modal, scheduler, scheduler_data, $rootScope, builderid) ->
            # prepare default values
            prepareFields = (fields) ->
                for field in fields
                    if field.type == "nested"
                        prepareFields(field.fields)
                    else
                        field.value = field.default
            prepareFields(scheduler_data.all_fields)
            angular.extend $scope,
                rootfield:
                    type: "nested"
                    layout: "simple"
                    fields: scheduler_data.all_fields
                    columns: 1
                sch: scheduler_data
                ok: ->
                    params =
                        builderid: builderid
                    fields_ref = {}
                    gatherFields = (fields) ->
                        for field in fields
                            field.errors = ""
                            if field.type == "nested"
                                gatherFields(field.fields)
                            else
                                params[field.fullName] = field.value
                                fields_ref[field.fullName] = field

                    gatherFields(scheduler_data.all_fields)
                    scheduler.control("force", params)
                    .then (res) ->
                        modal.modal.close(res.result)
                    ,   (err) ->
                        if err.data.error.code == -32602
                            for k, v of err.data.error.message
                                fields_ref[k].errors = v
                        $rootScope.$apply()

                cancel: ->
                    modal.modal.dismiss()
    ]
]
