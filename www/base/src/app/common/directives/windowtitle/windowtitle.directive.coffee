class WindowTitle extends Directive('common')
    constructor: ($rootScope, $timeout, $stateParams, $window, faviconService) -> return {
        restrict: 'A'
        link: ->
            listener = (event, toState) ->
                $timeout ->
                    faviconService.setFavIcon()
                    if toState.data and toState.data.pageTitle
                        if typeof(toState.data.pageTitle) == "function"
                            $window.document.title = toState.data.pageTitle($stateParams)
                        else
                            $window.document.title = toState.data.pageTitle
                    else if toState.data and toState.data.caption
                        $window.document.title = 'Buildbot: ' + toState.data.caption
                    else
                        $window.document.title = 'Buildbot'

            $rootScope.$on '$stateChangeSuccess', listener
            return
        }
