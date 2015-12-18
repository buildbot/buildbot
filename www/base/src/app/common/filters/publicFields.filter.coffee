class PublicFields extends Filter('common')
    constructor: ->
        return (object) ->
            if not object?
                return object
            object._publicfields ?= {}
            for k, v of object
                if k.indexOf('_') != 0 and object.hasOwnProperty(k)
                    object._publicfields[k] = v
            return object._publicfields
