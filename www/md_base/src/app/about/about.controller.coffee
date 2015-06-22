class About extends Controller
    fieldsToData: (fields) ->
        if fields
            return ([field.name, field.type] for field in fields)
        else
            return []

    processSpecs: (specs) ->
        return ({path: spec.path, fields: @fieldsToData(spec.type_spec.fields)} for spec in specs)

    constructor: (config, restService) ->
        @projectInfo =
            'Project Name': config.title
            'Project URL': config.titleURL
        @versions = config.versions
        @config = config
        @specs = []
        restService.get('application.spec').then (data) =>
            @specs = @processSpecs(data.specs)
