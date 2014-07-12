angular.module('buildbot.builders').controller 'forceDialogController',
    ['$scope', '$state', 'modal', 'scheduler', 'scheduler_data','$rootScope', 'builderid'
        ($scope, $state, modal, scheduler, scheduler_data, $rootScope, builderid) ->
            # prepare default values
            prepareFields = (fields) ->
                for field in fields
                    if field.type == 'nested'
                        prepareFields(field.fields)
                    else
                        field.value = field.default
            prepareFields(scheduler_data.all_fields)
            angular.extend $scope,
                rootfield:
                    type: 'nested'
                    layout: 'simple'
                    fields: scheduler_data.all_fields
                    columns: 1
                sch: scheduler_data
                ok: ->
                    params =
                        builderid: builderid
                    fields_ref = {}
                    gatherFields = (fields) ->
                        for field in fields
                            field.errors = ''
                            if field.type == 'nested'
                                gatherFields(field.fields)
                            else
                                params[field.fullName] = field.value
                                fields_ref[field.fullName] = field

                    gatherFields(scheduler_data.all_fields)
                    scheduler.control('force', params)
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