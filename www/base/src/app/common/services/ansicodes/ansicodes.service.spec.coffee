beforeEach module 'app'

describe 'ansicode service', ->
    ansicodesService = null

    injected = ($injector) ->
        ansicodesService = $injector.get('ansicodesService')

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


    it 'should provide correct split_ansi_line', ->
        ret = ansicodesService.split_ansi_line("\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.")
        expect(ret).toEqual [
            {class: 'ansi36', text: 'DEBUG [plugin]: '},
            {class: 'ansi39', text: 'Loading plugin karma-jasmine.'}]

    it 'should provide correct split_ansi_line for unknown modes', ->
        val = "\x1b[1A\x1b[2KPhantomJS 1.9.8 (Linux 0.0.0)"
        ret = ansicodesService.split_ansi_line(val)
        expect(ret).toEqual [
            { class: '', text: 'PhantomJS 1.9.8 (Linux 0.0.0)'}]

    it 'should provide correct ansi2html', ->
        ret = ansicodesService.ansi2html("\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.")
        expect(ret).toEqual "<span class='ansi36'>DEBUG [plugin]: </span><span class='ansi39'>Loading plugin karma-jasmine.</span>"
