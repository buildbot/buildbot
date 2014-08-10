beforeEach module 'app'

describe 'results service', ->
    resultsService = null

    injected = ($injector) ->
        resultsService = $injector.get('resultsService')

    beforeEach(inject(injected))

    it 'should provide correct results2class', ->
        results = resultsService.results
        results2class = (r) -> resultsService.results2class(results: r)

        expect(results2class(results.SUCCESS)).toBe("results_SUCCESS")
        expect(results2class(results.RETRY)).toBe("results_RETRY")
        expect(results2class(1234)).toBe("results_UNKNOWN")
        expect(resultsService.results2class(undefined)).toBe("results_UNKNOWN")
        expect(resultsService.results2class(results:undefined)).toBe("results_UNKNOWN")

        expect(resultsService.results2class
            results:undefined
            complete:false
            started_at:undefined
        ).toBe("results_UNKNOWN")

        expect(resultsService.results2class
            results:undefined
            complete:false
            started_at:10
            , "pulse"
        ).toBe("results_PENDING pulse")

    it 'should provide correct results2Text', ->
        results = resultsService.results
        results2text = (r) -> resultsService.results2text(results: r)

        expect(results2text(results.SUCCESS)).toBe("SUCCESS")
        expect(results2text(results.RETRY)).toBe("RETRY")
        expect(results2text(1234)).toBe("...")
        expect(resultsService.results2text(undefined)).toBe("...")
        expect(resultsService.results2text(results:undefined)).toBe("...")

        expect(resultsService.results2text
            results:undefined
            complete:false
            started_at:undefined
        ).toBe("...")

        expect(resultsService.results2text
            results:undefined
            complete:false
            started_at:10
        ).toBe("...")
