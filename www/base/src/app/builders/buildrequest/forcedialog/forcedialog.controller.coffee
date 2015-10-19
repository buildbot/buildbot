class forceDialog extends Controller
    constructor: ($scope, $state, modal, scheduler, $rootScope, builderid) ->
        # prepare default values
        prepareFields = (fields) ->
            for field in fields
                if field.fields?
                    prepareFields(field.fields)
                else
                    field.value = field.default
        prepareFields(scheduler.all_fields)
        angular.extend $scope,
            rootfield:
                type: 'nested'
                layout: 'simple'
                fields: scheduler.all_fields
                columns: 1
            sch: scheduler
            ok: ->
                params =
                    builderid: builderid
                fields_ref = {}
                gatherFields = (fields) ->
                    for field in fields
                        field.errors = ''
                        if field.fields?
                            gatherFields(field.fields)
                        else
                            params[field.fullName] = field.value
                            fields_ref[field.fullName] = field

                gatherFields(scheduler.all_fields)
                scheduler.control('force', params)
                .then (res) ->
                    modal.modal.close(res.result)
                ,   (err) ->
                    if err.data.error.code == -32602
                        for k, v of err.data.error.message
                            fields_ref[k].errors = v
                    else
                        $scope.error = err.data.error.message
            cancel: ->
                modal.modal.dismiss()
