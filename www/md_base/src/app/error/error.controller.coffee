class Error extends Controller
    constructor: (@$mdToast, @message) ->

    closeToast: ->
        @$mdToast.hide()
