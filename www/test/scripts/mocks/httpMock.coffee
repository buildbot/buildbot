window.decorateHttpBackend = ($httpBackend) ->
    ids = {}
    getNextId = (namespace) ->
        if not ids.hasOwnProperty(namespace)
            ids[namespace] = 0
        ids[namespace] += 1
        return ids[namespace]

    $httpBackend.epMatch = (a, b) ->
        a = a.split("/")
        b = b.split("/")
        if a.length != b.length
            return false
        for i in [0..a.length - 1]
            if a[i].indexOf("n:") == 0
                if not (/^\d$/).test(b[i])
                    return false
            else if a[i] isnt b[i]
                return false
        return true

    $httpBackend.epExample = (ep) ->
        ep = ep.split("/")
        for i in [0..ep.length - 1]
            if ep[i].indexOf("n:") == 0
                ep[i] = "1"
        return ep.join("/")

    $httpBackend.epLastPath = (path) ->
        splitpath = path.split("/")
        return splitpath[splitpath.length - 1]

    $httpBackend.resetIds = () ->
        ids = {}

    $httpBackend.buildDataValue = (ep, nItems) ->

        valueFromBaseType = (spec, hint) ->
            if spec.hasOwnProperty("fields")
                return valueFromSpec(spec, hint)
            hint ?= "mystring"
            if not spec.name?
                throw "no type: #{ spec } #{ tip }"
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
                when "sourced-properties"
                    return {prop: ['value', "source"]}
                else
                    throw "unknown type: #{ type }"

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
        for dataEp in window.dataspec
            if this.epMatch(dataEp.path, ep)
                if nItems?
                    ret = []
                    for i in [1..nItems]
                        ret.push(valueFromSpec(dataEp.type_spec, hint))
                else
                    ret = valueFromSpec(dataEp.type_spec, hint)
                return ret
        throw "endpoint not specified! #{ep}"

    $httpBackend.whenDataGET = (ep, opts) ->
        opts ?= {}
        opts.when = true  # callback for overriding automatically generated data
        return this.expectDataGET(ep, opts)
    $httpBackend.expectDataGET = (ep, opts) ->
        opts ?=
            nItems: undefined  # if nItems is defined, we will produce a collection
            override: undefined  # callback for overriding automaticly generated data
            when: undefined  # callback for overriding automatically generated data

        value = this.buildDataValue(ep, opts.nItems)
        if opts.override?
            opts.override(value)
        if opts.when?
            this.whenGET("api/v2/" + ep).respond(value)
        else
            this.expectGET("api/v2/" + ep).respond(value)
        return null

if window.describe?
    describe 'decorateHttpBackend', ->
        $httpBackend = {}
        injected = ($injector) ->
            $httpBackend = $injector.get('$httpBackend')
            decorateHttpBackend $httpBackend

        beforeEach(inject(injected))

        it 'should have correct endpoint matcher', ->
            expect($httpBackend.epMatch("change", "change")).toBe(true)
            expect($httpBackend.epMatch("change/n:foo", "change/1")).toBe(true)
            expect($httpBackend.epMatch("change/n:foo", "change/sd")).toBe(false)
            expect($httpBackend.epMatch("change/foo/bar/n:foobar/foo", "change/foo/bar/1/foo")).toBe(true)
            expect($httpBackend.epMatch("change/foo/bar/n:foobar/foo", "change/foo/bar/1/foo/")).toBe(false)

        it 'should have correct value builder for change', ->
            expected =
                files: ['myfiles']
                category: 'mycategory'
                repository: 'myrepository'
                author: 'myauthor'
                project: 'myproject'
                comments: 'mycomments'
                changeid: 1,
                codebase: 'mycodebase'
                link: 'http://link/link'
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
                    link: 'http://link/link'
                    branch: 'mybranch'
                    revision: 'myrevision'
                revision: 'myrevision'
                revlink: 'myrevlink'
                properties:
                    'prop': ['value', 'source']
                when_timestamp: 1

            value = $httpBackend.buildDataValue("change")
            for k, v of value
                expect(v).toEqual(expected[k])

            $httpBackend.resetIds()
            value = $httpBackend.buildDataValue("change", 2)

            # small hack to replace ones by twos for ids of the second change
            expected = [expected, JSON.parse(JSON.stringify(expected).replace(/1/g,"2"))]
            expect(value.length).toEqual(expected.length)
            for i in [0..value.length - 1]
                expect(value[i]).toEqual(expected[i])

        it 'should have value builder not crash for all data spec cases', ->
            for dataEp in window.dataspec
                $httpBackend.buildDataValue($httpBackend.epExample(dataEp.path))
