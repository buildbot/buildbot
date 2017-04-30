class Loginbar extends Directive('common')
    constructor: ->
        return {
            controller: '_loginbarController'
            replace: true
            restrict: 'E'
            scope: {}
            templateUrl: 'views/loginbar.html'
        }
class AutoLogin extends Config
    constructor: (config) ->
        if config.auth? and config.auth.autologin and config.user.anonymous and config.auth.oauth2
            window.stop()
            document.location = "auth/login?redirect=" + document.location.hash.substr(1)


class _loginbar extends Controller('common')
    constructor: ($scope, config, $http, $location) ->
        baseurl = $location.absUrl().split("#")[0]
        $scope.username = ""
        $scope.password = ""
        $scope.loginCollapsed = 1
        $scope.config = config
        # as the loginbar is never reloaded, we need to update the redirect
        # when the hash changes
        $scope.$watch (-> document.location.hash), ->
            $scope.redirect = document.location.hash.substr(1)
        _.assign($scope, config.user)
