class ExceptionHandlerDecorator extends Config
    constructor: ($provide) ->
        name = 'error'
        $provide.decorator '$exceptionHandler', ($delegate, $injector) ->
            return (exception, cause) ->
                $mdToast = $injector.get('$mdToast')
                $mdToast.show
                    templateUrl: "views/#{name}.html"
                    controller: "#{name}Controller"
                    controllerAs: name
                    position: 'bottom right'
                    hideDelay: false
                    locals:
                        message: exception.message or exception
                $delegate(exception, cause)
        return null
