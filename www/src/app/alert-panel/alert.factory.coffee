class Alert extends Factory
    constructor: ($rootScope) ->
        alert = (msg, type) ->
            type ?= 'danger'
            $rootScope.$broadcast 'alert', type:type, msg: msg

        alert.error = (msg) ->
            alert msg, 'danger'

        alert.warning = (msg) ->
            alert msg, 'info'

        alert.success = (msg) ->
            alert msg, 'success'
        window.alert = alert
        return alert