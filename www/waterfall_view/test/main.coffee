# Mocked module dependencies
angular.module('common', []).constant 'config', plugins: waterfall_view: {
    limit: 2
}
angular.module('ngAnimate', [])
# Mock modalService
module ($provide) ->
    $provide.service '$modal', ->
    $provide.service '$modalInstance', ->
    null