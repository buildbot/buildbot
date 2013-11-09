# using window.define prevents r.js to include everything of ace
# Ace is already modular, and is better kept this way (e.g. language support is in modules)
window.define ["codeparameter/ace/ace"], ->
    # add ui-ace to the list of needed modules
    angular.module('app').requires.push("ui.ace")
    angular.module('app').requires.push("codeparameter-templates-views")

    # defines custom field directives which only have templates
    _.each [ 'codefield' ], (fieldtype) ->
        angular.module('app').directive fieldtype, ->
            replace: false
            restrict: 'E'
            scope: false
            templateUrl: "codeparameter/views/directives/#{fieldtype}.html"
