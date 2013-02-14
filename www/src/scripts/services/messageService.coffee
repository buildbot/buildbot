angular.module('app').factory 'messageService', ['$log', '$rootScope', ($log, $rootScope) ->
	publish = (name, parameters) ->
		parameters.timeStamp = new Date()

		$rootScope.$broadcast name, parameters

	subscribe = (name, listener) ->
		$rootScope.$on name, listener

	{publish, subscribe}
]