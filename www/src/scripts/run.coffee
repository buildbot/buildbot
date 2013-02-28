angular.module('app').run ['$rootScope', '$log', ($rootScope, $log) ->
	# fire an event related to the current route
	$rootScope.$on '$routeChangeSuccess', (event, currentRoute, priorRoute) ->
		$rootScope.$broadcast "#{currentRoute.controller}$routeChangeSuccess", currentRoute, priorRoute
]