angular.module('buildbot.console_view').controller 'modalController',
    ['$rootScope', '$modalInstance', 'selectedBuild', class
        constructor: ($rootScope, @$modalInstance, @selectedBuild) ->
            $rootScope.$on '$stateChangeStart', => @close()

        close: ->
            @$modalInstance.dismiss()
    ]
