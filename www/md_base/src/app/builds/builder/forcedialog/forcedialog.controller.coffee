class ForceDialog extends Controller

    fields: {}
    field_errors: null

    cancel: ->
        @$mdDialog.hide()

    confirm: ->
        param = builderid: @builder.builderid
        _.extend param, @fields
        console.log param
        @scheduler.control('force', param)
            .then =>
                @field_errors = null
                @$mdDialog.hide()
            , (data) =>
                if data.error.code == -32602
                    @field_errors = data.error.message
                else
                    alert "Unexpected error occurs, please try again."
                    @field_errors = null

    constructor: (@builder, @scheduler, @dataService, @$mdDialog) ->
        parseFields = (field) =>
            if field.nested
                parseFields(subfield) for subfield in field.fields
            else if field.name
                @fields[field.name] = field.default

        parseFields(field) for field in @scheduler.all_fields

