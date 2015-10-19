class PublicFields extends Filter('common')
    constructor: ->
        return (object) ->
            copy = angular.copy(object)
            for k of object
                if k.indexOf('_') == 0 then delete copy[k]
            return object
