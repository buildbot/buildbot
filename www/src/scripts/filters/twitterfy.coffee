angular.module('app').filter 'twitterfy', ['$log', ($log) -> (username) ->
	"@#{username}"
]