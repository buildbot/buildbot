/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class WindowTitle {
    constructor($rootScope, $timeout, $stateParams, $window, faviconService) { return {
        restrict: 'A',
        link() {
            const listener = (event, toState) =>
                $timeout(function() {
                    faviconService.setFavIcon();
                    if (toState.data && toState.data.pageTitle) {
                        if (typeof(toState.data.pageTitle) === "function") {
                            return $window.document.title = toState.data.pageTitle($stateParams);
                        } else {
                            return $window.document.title = toState.data.pageTitle;
                        }
                    } else if (toState.data && toState.data.caption) {
                        return $window.document.title = `Buildbot: ${toState.data.caption}`;
                    } else {
                        return $window.document.title = 'Buildbot';
                    }
                })
            ;

            $rootScope.$on('$stateChangeSuccess', listener);
        }
        }; }
}


angular.module('common')
.directive('windowTitle', ['$rootScope', '$timeout', '$stateParams', '$window', 'faviconService', WindowTitle]);
