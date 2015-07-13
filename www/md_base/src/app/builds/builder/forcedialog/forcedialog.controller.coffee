class ForceDialog extends Controller

    fields: {}

    cancel: ->
        @$mdDialog.hide()

    confirm: ->
        @$mdDialog.hide()

    constructor: (@scheduler, @dataService, @$mdDialog) ->
        parseFields = (field) =>
            if field.nested
                parseFields(subfield) for subfield in field.fields
            else
                @fields[field.name] = field.default

        parseFields(field) for field in @scheduler.all_fields
