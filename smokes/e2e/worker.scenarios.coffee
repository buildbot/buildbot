# coffee script
# test goal: checks the capability to navigate on about web page
# to use previous and next link

workerPage = require('./pages/worker.coffee')
settingsPage = require('./pages/settings.coffee')

describe('', () ->
    worker = null
    builder = null
    settings = null

    beforeEach(() ->
        worker = new workerPage('runtests')
        settings = new settingsPage('runtests')
    )

    describe 'check worker page', () ->
        it 'should navigate to the worker page, check the one builder inside', () ->
            settings.goSettings()
            settings.changeShowWorkerBuilders(true)
            settings.checkShowWorkerBuilders(true)
            worker.goWorker()
            worker.checkWorkerPage()
            worker.checkHrefPresent()
            builder = worker.goBuilderLink('slowruntests')
            builder.checkBuilderURL()

    describe 'check worker page', () ->
        it 'should navigate to the worker page, check the one builder inside', () ->
            settings.goSettings()
            settings.changeShowWorkerBuilders(true)
            settings.checkShowWorkerBuilders(true)
            worker.goWorker()
            worker.checkWorkerPage()
            worker.checkHrefPresent()
            builder = worker.goBuilderLink('runtests')
            builder.checkBuilderURL()

)
