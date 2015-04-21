class About extends Controller

    constructor: (config) ->
        @projectInfo =
            'Project Name': config.title
            'Project URL': config.titleURL
        @versions = config.versions
        @config = config
