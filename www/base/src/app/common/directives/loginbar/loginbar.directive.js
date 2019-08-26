/*
 * decaffeinate suggestions:
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class Loginbar {
    constructor() {
        return {
            controller: '_loginbarController',
            replace: true,
            restrict: 'E',
            scope: {},
            template: require('./loginbar.tpl.jade'),
        };
    }
}
class AutoLogin {
    constructor(config) {
        if ((config.auth != null) && config.auth.autologin && config.user.anonymous && config.auth.oauth2) {
            window.stop();
            document.location = `auth/login?redirect=${document.location.hash.substr(1)}`;
        }
    }
}


class _loginbar {
    constructor($scope, config, $http, $location) {
        const baseurl = $location.absUrl().split("#")[0];
        $scope.username = "";
        $scope.password = "";
        $scope.loginCollapsed = 1;
        $scope.config = config;
        // as the loginbar is never reloaded, we need to update the redirect
        // when the hash changes
        $scope.$watch((() => document.location.hash),
                      () => $scope.redirect = document.location.hash.substr(1));
        _.assign($scope, config.user);
    }
}


angular.module('common')
.directive('loginbar', [Loginbar])
.controller('_loginbarController', ['$scope', 'config', '$http', '$location', _loginbar]);

angular.module('app')
.config(['config', AutoLogin]);
