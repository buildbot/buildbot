beforeEach module 'app'

describe 'ansicode service', ->
    ansicodesService = null

    injected = ($injector) ->
        ansicodesService = $injector.get('ansicodesService')

    beforeEach(inject(injected))

    runTest = (string, expected...) ->
        ret = ansicodesService.parseAnsiSgr(string)
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
        ret = ansicodesService.splitAnsiLine("\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.")
        expect(ret).toEqual [
            {class: 'ansi36', text: 'DEBUG [plugin]: '},
            {class: '', text: 'Loading plugin karma-jasmine.'}]

    it 'should provide correct split_ansi_line for nested codes', ->
        ret = ansicodesService.splitAnsiLine("\x1b[1m\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.")
        expect(ret).toEqual [
            {class: 'ansi1 ansi36', text: 'DEBUG [plugin]: '},
            {class: '', text: 'Loading plugin karma-jasmine.'}]

    it 'should provide correct split_ansi_line for reset codes', ->
        # code sequence from protractor
        ret = ansicodesService.splitAnsiLine("\x1b[32m.\x1b[0m\x1b[31mF\x1b[0m\x1b[32m.\x1b[39m\x1b[32m.\x1b[0m")
        expect(ret).toEqual [
            {class: "ansi32", text: "."},
            {class: "ansi31", text: "F"},
            {class: "ansi32", text: "."},
            {class: "ansi32", text: "."},
         ]

    it 'should provide correct split_ansi_line for 256 colors', ->
        ret = ansicodesService.splitAnsiLine("\x1b[48;5;71mDEBUG \x1b[38;5;72m[plugin]: \x1b[39mLoading plugin karma-jasmine.")
        expect(ret).toEqual [
            {class: 'ansibg-71', text: 'DEBUG '},
            {class: 'ansifg-72', text: '[plugin]: '},
            {class: '', text: 'Loading plugin karma-jasmine.'}]

    it 'should provide correct split_ansi_line for joint codes', ->
        ret = ansicodesService.splitAnsiLine("\x1b[1;36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.")
        expect(ret).toEqual [
            {class: 'ansi1 ansi36', text: 'DEBUG [plugin]: '},
            {class: '', text: 'Loading plugin karma-jasmine.'}]

    it 'should provide correct split_ansi_line for unsupported modes', ->
        val = "\x1b[1A\x1b[2KPhantomJS 1.9.8 (Linux 0.0.0)"
        ret = ansicodesService.splitAnsiLine(val)
        expect(ret).toEqual [
            { class: '', text: 'PhantomJS 1.9.8 (Linux 0.0.0)'}]

    it 'should provide correct ansi2html', ->
        ret = ansicodesService.ansi2html("\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.")
        expect(ret).toEqual "<span class='ansi36'>DEBUG [plugin]: </span><span class=''>Loading plugin karma-jasmine.</span>"

    it 'should provide correct color cube generator', ->
        ret = ansicodesService.generateStyle()
        expect(ret).toContain('pre.log .ansibg-232 { background-color: #090909; }')
        expect(ret).toContain('pre.log .ansibg-241 { background-color: #626262; }')
        expect(ret).toContain('pre.log .ansifg-209 { color: #f96; }')


    it 'should inject generated style only once', ->
        before = document.getElementsByTagName("style").length
        ansicodesService.injectStyle()
        after1 = document.getElementsByTagName("style").length
        ansicodesService.injectStyle()
        after2 = document.getElementsByTagName("style").length
        expect(after1).toEqual(before + 1)
        expect(after2).toEqual(before + 1)
