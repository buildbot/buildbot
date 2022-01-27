/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class WindowTitle {
    constructor($transitions, $timeout, $stateParams, $window, faviconService, config) { return {
        restrict: 'A',
        link() {
            const listener = (transition) =>
                $timeout(function() {
                    const toState = transition.to();
                    faviconService.setFavIcon();
                    if (toState.data && toState.data.pageTitle) {
                        if (typeof(toState.data.pageTitle) === "function") {
                            $window.document.title = toState.data.pageTitle($stateParams);
                        } else {
                            $window.document.title = toState.data.pageTitle;
                        }
                    } else if (toState.data && toState.data.caption) {
                        $window.document.title = `${config.title}: ${toState.data.caption}`;
                    } else {
                        $window.document.title = config.title;
                    }
                })
            ;

            $transitions.onSuccess({}, listener);
        }
        }; }
}


angular.module('common')
.directive('windowTitle', ['$transitions', '$timeout', '$stateParams', '$window', 'faviconService', 'config', WindowTitle]);
