app = angular.module('app')
# add ui-ace to the list of needed modules
app.requires.push("ui.ace")

# setup ace to fetch its module from the plugin baseURL
app.run  (config) ->
    window.ace.config.set("basePath", config.url + "codeparameter")


# defines custom field directives which only have templates
app.directive 'codefield', ->
    replace: false
    restrict: 'E'
    scope: false
    templateUrl: "codeparameter/views/codefield.html"
