beforeEach module 'app'

describe 'fields service', ->
    fieldsService = null

    injected = ($injector) ->
        fieldsService = $injector.get('fieldsService')

    beforeEach(inject(injected))

    it 'should provide correct checkbox button', ->
        checkbox = (name, model) -> fieldsService.checkbox(name, model)

        model = true
        expect(checkbox("test").name).toBe("test")
        expect(checkbox(1234).name).toBe("1234")
        expect(checkbox(1234).value).toBeUndefined()
        expect(checkbox(1234, model).value).toBeTruthy()

    it 'should provide correct radio button', ->
        model = "answer1"
        expect(fieldsService.radio("test").name).toBe("test")
        expect(fieldsService.radio(1234).name).toBe("1234")
        expect(fieldsService.radio("test", model, "answer1", "answer2").name).toBe("test")

        expect(fieldsService.radio("test", model).answers[0]).toBe("yes")
        expect(fieldsService.radio("test", model).answers[1]).toBe("no")
        expect(fieldsService.radio("test", model).value).toBe("answer1")
        expect(fieldsService.radio("test", model, "answer1", "answer2").answers[0]).toBe("answer1")
        expect(fieldsService.radio("test", model, "answer1", "answer2").answers[1]).toBe("answer2")
        expect(fieldsService.radio("test", model, "answer1", "answer2").value).toBe("answer1")
        expect(fieldsService.radio("test", undefined).value).toBeUndefined()
        expect(fieldsService.radio("test", undefined, "answer1").value).toBeUndefined()

