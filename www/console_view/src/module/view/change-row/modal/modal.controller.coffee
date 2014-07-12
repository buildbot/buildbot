angular.module('buildbot.console_view').controller 'modalController',
    ['$modalInstance', 'selectedBuild', class
        constructor: ($modalInstance, @selectedBuild) ->
            @close = ->
                $modalInstance.dismiss()
    ]