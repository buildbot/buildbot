angular.module('app').factory 'alert', ['$rootScope', ($rootScope) ->

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
]
angular.module('app').config ['$httpProvider', ($httpProvider) ->
    $httpProvider.responseInterceptors.push ["alert", "$q", (alert, $q) ->
         return (promise) ->
            promise.then (res)->
                res
            , (res) ->
                if res.config.url.indexOf("views") == 0 and res.status == 404
                    alert.error "view does not exist: " + res.config.url
                else
                    alert.error res.data
                $q.reject res
                console.log res
    ]

]
