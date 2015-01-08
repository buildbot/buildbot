class fieldsService extends Factory('common')
  constructor: ->
    return {

        checkbox: (name, model) ->
            if localStorage.getItem("#{name}")?
                initial_value = localStorage.getItem("#{name}") is "true"
            else
                initial_value = model 

            field = 
                type: 'checkbox'
                name: "#{name}"
                value: initial_value
            return field

        radio: (name, model, specific_answers...) ->
            default_answers = ["yes", "no"]
            answers = default_answers
            if specific_answers.length > 0
                answers = specific_answers

            if localStorage.getItem("#{name}")?
                initial_value = localStorage.getItem("#{name}")
            else
                initial_value = model

            field = 
                name: "#{name}"
                type: 'radio'
                value: initial_value
                answers: answers
            return field

        input: (name, model) ->
            if localStorage.getItem("#{name}")?
                initial_value = localStorage.getItem("#{name}")
            else
                initial_value = model

            field = 
                name: "#{name}"
                type: 'text'
                value: initial_value
            return field

    }

