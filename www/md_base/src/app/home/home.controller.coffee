class Home extends Controller
    title: ''
    titleURL: ''
    constructor: (config) ->
        @title = config.title
        @titleURL = config.titleURL
