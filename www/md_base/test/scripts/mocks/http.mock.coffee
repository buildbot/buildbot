window.decorateHttpBackend = ($httpBackend) ->
    ids = {}
    getNextId = (namespace) ->
        if not ids.hasOwnProperty(namespace)
            ids[namespace] = 0
        ids[namespace] += 1
        return ids[namespace]

    $httpBackend.epExample = (ep) ->
        ep = ep.split("/")
        for i in [0..ep.length - 1]
            if ep[i].indexOf("n:") == 0
                ep[i] = "1"
            if ep[i].indexOf("i:") == 0
                ep[i] = "id"
        return ep.join("/")

    $httpBackend.epRegexp = (ep) ->
        ep = ep.split("/")
        for i in [0..ep.length - 1]
            if ep[i].indexOf("n:") == 0
                ep[i] = "\\d+"
            if ep[i].indexOf("i:") == 0
                ep[i] = "[a-zA-Z_-][a-zA-Z0-9_-]*"
        return RegExp("^"+ep.join("/")+"$")

    $httpBackend.epLastPath = (path) ->
        splitpath = path.split("/")
        return splitpath[splitpath.length - 1]

    $httpBackend.resetIds = ->
        ids = {}

    $httpBackend.buildDataValue = (ep, nItems) ->

        valueFromBaseType = (spec, hint) ->
            if spec.hasOwnProperty("fields")
                return valueFromSpec(spec, hint)
            hint ?= "mystring"
            if not spec.name?
                throw Error("no type: #{ JSON.stringify(spec) } #{ hint }")
            type = spec.name
            switch type
                when "string"
                    return hint
                when "binary"
                    return hint
                when "identifier"
                    return hint + getNextId(hint)
                when "integer"
                    return getNextId(hint)
                when "boolean"
                    return false
                when "jsonobject"
                    return {}
                when "link"
                    return "http://link/link"
                when "datetime"
                    return getNextId(hint)
                when "sourced-properties"
                    return {prop: ['value', "source"]}
                else
                    throw Error("unknown type: #{ type }")

        valueFromSpec = (spec, basehint) ->
            ret = {}
            for field in spec.fields
                hint = "my" + field.name
                if field.name == "name"
                    hint = basehint
                if field.type is "list"
                    ret[field.name] = [valueFromBaseType(field.type_spec.of, hint)]
                else
                    ret[field.name] = valueFromBaseType(field.type_spec, hint)
            return ret

        hint = $httpBackend.epLastPath(ep).replace("n:","")
        if not window.dataspec?
            throw Error("dataspec is not available in test environment?!")
        for dataEp in window.dataspec
            dataEp.re ?= this.epRegexp(dataEp.path)
            if dataEp.re.test(ep)
                if nItems?
                    data = []
                    for i in [0..nItems - 1] by 1
                        data.push(valueFromBaseType(dataEp.type_spec, hint))
                else
                    data = [valueFromBaseType(dataEp.type_spec, hint)]
                ret = {meta:{links: [] }}
                ret[dataEp.plural] = data
                return ret
        throw Error("endpoint not specified! #{ep}")

    $httpBackend.whenDataGET = (ep, opts) ->
        opts ?= {}
        opts.when = true  # use whenGetET instead of expectGET
        return this.expectDataGET(ep, opts)
    $httpBackend.expectDataGET = (ep, opts) ->
        opts ?=
            nItems: undefined  # if nItems is defined, we will produce a collection
            override: undefined  # callback for overriding automaticly generated data
            when: undefined  # use whenGET instead of expectGET
        ep_query = ep.split("?")
        value = this.buildDataValue(this.epExample(ep_query[0]), opts.nItems)

        if opts.override?
            opts.override(value)
        if opts.when?
            this.whenGET(this.epRegexp("api/v2/" + ep)).respond(value)
        else
            this.expectGET("api/v2/" + ep).respond(value)
        return null
    $httpBackend.expectGETSVGIcons = (override) ->
        override = '<svg><g id="test"></g></svg>'
        this.expectGET('/icons/iconset.svg').respond(200, override)
    $httpBackend.whenGETSVGIcons = (override) ->
        override = '<svg><g id="test"></g></svg>'
        this.whenGET('/icons/iconset.svg').respond(200, override)

if window.describe?
    describe 'decorateHttpBackend', ->
        $httpBackend = {}
        injected = ($injector) ->
            $httpBackend = $injector.get('$httpBackend')
            decorateHttpBackend $httpBackend

        beforeEach(inject(injected))

        it 'should have correct endpoint matcher', ->
            epMatch = (a,b) ->
                re = $httpBackend.epRegexp(a)
                return re.test(b)
            expect(epMatch("change", "change")).toBe(true)
            expect(epMatch("change/n:foo", "change/1")).toBe(true)
            expect(epMatch("change/n:foo", "change/sd")).toBe(false)
            expect(epMatch("change/foo/bar/n:foobar/foo", "change/foo/bar/1/foo")).toBe(true)
            expect(epMatch("change/foo/bar/n:foobar/foo", "change/foo/bar/1/foo/")).toBe(false)

        it 'should have correct value builder for change', ->
            expected =
                files: ['myfiles']
                category: 'mycategory'
                parent_changeids: [1]
                repository: 'myrepository'
                author: 'myauthor'
                project: 'myproject'
                comments: 'mycomments'
                changeid: 1,
                codebase: 'mycodebase'
                branch: 'mybranch'
                sourcestamp:
                    codebase: 'mycodebase'
                    ssid: 1
                    repository: 'myrepository'
                    created_at: 1
                    patch:
                        body: 'mybody'
                        comment: 'mycomment'
                        patchid: 1
                        level: 1
                        author: 'myauthor'
                        subdir: 'mysubdir'
                    project: 'myproject'
                    branch: 'mybranch'
                    revision: 'myrevision'
                revision: 'myrevision'
                revlink: 'myrevlink'
                properties:
                    'prop': ['value', 'source']
                when_timestamp: 1

            value = $httpBackend.buildDataValue("changes").changes[0]
            for k, v of value
                expect(v).toEqual(expected[k])

            $httpBackend.resetIds()
            value = $httpBackend.buildDataValue("changes", 2).changes

            # small hack to replace ones by twos for ids of the second change
            expected = [expected, JSON.parse(JSON.stringify(expected).replace(/1/g,"2"))]
            expect(value.length).toEqual(expected.length)
            for i in [0..value.length - 1]
                expect(value[i]).toEqual(expected[i])

        it 'should have value builder not crash for all data spec cases', ->
            for dataEp in window.dataspec
                $httpBackend.buildDataValue($httpBackend.epExample(dataEp.path))
