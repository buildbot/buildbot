# using window.define prevents r.js to include everything of ace
# Ace is already modular, and is better kept this way (e.g. language support is in modules)
window.define ["codeparameter/scripts/ace/ace"], ->
    # add ui-ace to the list of needed modules
    angular.module('buildbot.common').requires.push("ui.ace")

    # defines custom field directives which only have templates
    _.each [ 'codefield' ], (fieldtype) ->
        angular.module('buildbot.common').directive fieldtype, ->
            replace: false
            restrict: 'E'
            scope: false
            templateUrl: "codeparameter/views/#{fieldtype}.html"
