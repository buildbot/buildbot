beforeEach module 'app'

fdescribe 'ansicode service', ->
    ansicodesService = null
    console.log "before"

    injected = ($injector) ->
        console.log "inject"
        ansicodesService = $injector.get('ansicodesService')
        console.log ansicodesService

    beforeEach(inject(injected))

    runTest = (string, expected...) ->
        ret = ansicodesService.parse_ansi_sgr(string)
        expect(ret).toEqual(expected)

    it "test_ansi0m", ->
        runTest("mfoo", "foo", [])

    it "test ansi1m" , ->
        runTest("33mfoo", "foo", ["33"])

    it "test ansi2m" , ->
        runTest("1;33mfoo", "foo", ["1", "33"])

    it "test ansi5m" , ->
        runTest("1;2;3;4;33mfoo", "foo", ["1", "2", "3", "4", "33"])

    it "test ansi_notm" , ->
        runTest("33xfoo", "foo", [])

    it "test ansi_invalid" , ->
        runTest("<>foo", "\x1b[<>foo", [])

    it "test ansi_invalid_start_by_semicolon" , ->
        runTest(";3m", "\x1b[;3m", [])

    it 'should provide correct parse_ansi_sgr', ->
        parse_ansi_sgr = ansicodesService.parse_ansi_sgr
