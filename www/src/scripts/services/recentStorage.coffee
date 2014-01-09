###
Services that persists and retrieves recents from localStorage. (from todomvc
example)
###

angular.module('app').factory 'recentStorage',
['$log', ($log) ->
    STORAGE_ID = "buildbot-angularjs"
    get: ->
        JSON.parse localStorage.getItem(STORAGE_ID) or "[]"

    put: (recent) ->
        localStorage.setItem(STORAGE_ID, JSON.stringify(recent))
]
