class Loginbar extends Directive('common')
    constructor: ->
        return {
            controller: '_loginbarController'
            replace: true
            restrict: 'E'
            scope: {}
            templateUrl: 'views/loginbar.html'
        }

class _loginbar extends Controller('common')
    constructor: ($scope, config, $http, $location) ->
        baseurl = $location.absUrl().split("#")[0]
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
                url: "#{baseurl}auth/login"
            .success (data, status) ->
                window.location.reload()

        $scope.logout = ->
            $http.defaults.headers.common = {}
            $http
                method: "GET"
                url: "#{baseurl}auth/logout"
            .success (data, status) ->
                window.location.reload()
        $scope.loginoauth2 = ->
            $http
                method: "GET"
                url: "#{baseurl}auth/login"
            .success (data, status) ->
                document.location = data
        if config.auth.autologin and config.user.anonymous and config.auth.oauth2
            $scope.loginoauth2()
