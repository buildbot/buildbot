class ForceDialog extends Controller
    data: {}
    fields: []
    field_errors: null

    cancel: ->
        @$mdDialog.hide()

    confirm: ->
        param = builderid: @builder.builderid
        _.extend param, @data
        @forceBuild param

    forceBuildSuccess: ->
        @field_errors = null
        @$mdDialog.hide()

    forceBuildFail: (error) ->
        if error.code == -32602
            @field_errors = data.error.message
        else
            alert "Unexpected error occurs, please try again."
            @field_errors = null

    forceBuild: (param) ->
        res = @restService.post 'forceschedulers/force',
            id: @dataService.getNextId()
            jsonrpc: '2.0'
            method: 'force'
            params: param
        res.then (=> @forceBuildSuccess()), (data) => @forceBuildFail(data.error)

    constructor: (@builder, @scheduler, @dataService, @restService, @$mdDialog) ->
        @fields = @scheduler.all_fields

        parseFields = (field) =>
            if field.nested
                parseFields(subfield) for subfield in field.fields
            else if field.name
                @data[field.name] = field.default

        parseFields(field) for field in @fields

