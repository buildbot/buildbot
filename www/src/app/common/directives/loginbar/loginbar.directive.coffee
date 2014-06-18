angular.module('buildbot.common').directive 'loginbar',
[ ->
    controller = [
        '$scope', 'config', '$http', ($scope, config, $http) ->
            $scope.username = ""
            $scope.password = ""
            $scope.loginCollapsed = 1
            $scope.config = config
            _.assign($scope, config.user)
            $scope.login = ->
                $http.defaults.headers.common =
                    "Access-Control-Request-Headers": "accept, origin, authorization"
                auth = "Basic #{btoa($scope.username + ':' + $scope.password)}"
                $http.defaults.headers.common['Authorization'] = auth
                $http
                    method: "GET"
                    url: "#{config.url}auth/login"
                .success (data, status) ->
                    window.location.reload()

            $scope.logout = ->
                $http.defaults.headers.common = {}
                $http
                    method: "GET"
                    url: "#{config.url}auth/logout"
                .success (data, status) ->
                    window.location.reload()
            $scope.loginoauth2 = ->
                $http
                    method: "GET"
                    url: "#{config.url}auth/login"
                .success (data, status) ->
                    document.location = data
            if config.auth.autologin and config.user.anonymous and config.auth.oauth2
                $scope.loginoauth2()
    ]
    controller: controller
    replace: true
    restrict: 'E'
    scope: {}
    templateUrl: 'views/loginbar.html'
]
