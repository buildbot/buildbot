class forceDialog extends Controller
    constructor: ($scope, config, $state, modal, schedulerid, $rootScope, builderid, dataService) ->
        dataService.getForceschedulers(schedulerid, subscribe: false).onChange = (schedulers) ->
            scheduler = schedulers[0]
            all_fields_by_name = {}

            # prepare default values
            prepareFields = (fields) ->
                for field in fields
                    all_fields_by_name[field.fullName] = field
                    # give a reference of other fields to easily implement
                    # autopopulate
                    field.all_fields_by_name = all_fields_by_name
                    field.errors = ''
                    field.haserrors = false
                    if field.fields?
                        prepareFields(field.fields)
                    else
                        field.value = field.default
                        # if field type is username, then we just hide the field
                        # the backend will fill the value automatically
                        if field.type == 'username'
                            field.type = "text"
                            user = config.user
                            if user.email?
                                field.type = "text"
                                field.hide = true
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
                    for name, field of all_fields_by_name
                        params[name] = field.value

                    scheduler.control('force', params)
                    .then (res) ->
                        modal.modal.close(res.result)
                    ,   (err) ->
                        if err is null
                            return
                        if err.error.code == -32602
                            for k, v of err.error.message
                                all_fields_by_name[k].errors = v
                                all_fields_by_name[k].haserrors = true
                        else
                            $scope.error = err.error.message
                cancel: ->
                    modal.modal.dismiss()
