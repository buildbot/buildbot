###
    Recent storage service
###

class RecentStorage extends Factory('common')
    constructor: ($q, $window, $rootScope) ->
        self = this
        db = null
        setUp = false
        self =
            open: ->
                if not $window.indexedDB?
                    return $q.reject('IndexedDB is not supported')

                if setUp
                    return $q.when(true)

                deferred = $q.defer()
                indexedDB = $window.indexedDB

                openRequest = indexedDB.open('Recent', 5)
                openRequest.onupgradeneeded = (e) ->
                    thisDB = e.target.result

                    if not thisDB.objectStoreNames.contains('recent_builders')
                        thisDB.createObjectStore 'recent_builders', { keyPath: 'link' }
                    if not thisDB.objectStoreNames.contains('recent_builds')
                        thisDB.createObjectStore 'recent_builds', { keyPath: 'link' }

                openRequest.onsuccess = (e) ->
                    db = e.target.result
                    setUp = true
                    $rootScope.$apply ->
                        deferred.resolve(true)

                openRequest.onerror = (e) ->
                    $rootScope.$apply ->
                        deferred.reject('Database error:' + e.toString())

                return deferred.promise

            addRecent: (link, recent) ->
                return self.open().then ->
                    transaction = db.transaction([link], 'readwrite')
                    store = transaction.objectStore(link)
                    store.add(recent)

            getRecentLinks: (link) ->
                return self.open().then ->
                    deferred = $q.defer()

                    transaction = db.transaction([link], 'readwrite')
                    store = transaction.objectStore(link)
                    cursorRequest = store.openCursor()

                    cursorRequest.onerror = (e) ->
                        $rootScope.$apply ->
                            deferred.reject('Database error:' + e.toString())

                    recents = []
                    cursorRequest.onsuccess = (e) ->
                        cursor = e.target.result
                        if cursor?
                            recents.push(cursor.value)
                            cursor.continue()

                    transaction.oncomplete = ->
                        $rootScope.$apply ->
                            deferred.resolve(recents)

                    return deferred.promise

            clear: (link) ->
                return self.open().then ->
                    deferred = $q.defer()
                    transaction = db.transaction([link], 'readwrite')
                    store = transaction.objectStore(link)
                    req = store.clear()
                    req.onerror = (e) ->
                        $rootScope.$apply ->
                            deferred.reject('Database error:' + e.toString())

                    req.onsuccess = (e) ->
                        $rootScope.$apply ->
                            deferred.resolve(null)
                    return deferred.promise

        service =
            addBuild: (build) ->
                return self.addRecent('recent_builds', build)

            addBuilder: (builder) ->
                return self.addRecent('recent_builders', builder)

            getBuilds: ->
                return self.getRecentLinks('recent_builds')

            getBuilders: ->
                return self.getRecentLinks('recent_builders')

            getAll: ->
                return $q.all {
                    recent_builds: service.getBuilds(),
                    recent_builders: service.getBuilders()
                }

            clearAll: ->
                return $q.all [
                    self.clear('recent_builds')
                    self.clear('recent_builders')
                ]

        return service