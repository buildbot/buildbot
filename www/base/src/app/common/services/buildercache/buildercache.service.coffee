# builder data used everywhere in the UI, so we implement a simple cache

# TODO this caching mechanism needs to be implemented eventually in data module
# Its much more complicated to do this generically, and keep the event mechanism,
# this is why we do this temporary workaround

# Objects returned by this service cannot use onNew/onUpdate mechanism of data module (as they are shared)

class buildersService extends Factory('common')
    constructor: ($log, dataService) ->
        # we use an always on dataService instance
        data = dataService.open()
        cache = {}
        return {
            getBuilder: (id) ->
                if cache.hasOwnProperty(id)
                    return cache[id]
                else
                    cache[id] = {}
                    data.getBuilders(id).onNew = (builder) ->
                        _.assign(cache[id], builder)
                    return cache[id]
        }
