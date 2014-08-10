app = angular.module('buildbot.codeparameter', ["ui.ace"])
angular.module('app').requires.push("buildbot.codeparameter")

# setup ace to fetch its module from the plugin baseURL
app.run  (config) ->
    window.ace.config.set("basePath", config.url + "codeparameter")


# defines custom field directives which only have templates
app.directive 'codefield', ->
    replace: false
    restrict: 'E'
    scope: false
    templateUrl: "buildbot.codeparameter/views/codefield.html"
