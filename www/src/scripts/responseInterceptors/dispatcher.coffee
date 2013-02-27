angular.module('app').config ['$httpProvider', ($httpProvider) ->
	$httpProvider.responseInterceptors.push ['$log', '$rootScope', '$q', ($log, $rootScope, $q) ->
		success = (response) ->
			$rootScope.$broadcast "success:#{response.status}", response

			response

		error = (response) ->
			deferred = $q.defer()

			$rootScope.$broadcast "error:#{response.status}", response

			$q.reject response

		(promise) ->
			promise.then success, error
	]
]