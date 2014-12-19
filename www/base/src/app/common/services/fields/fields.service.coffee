class fieldsService extends Factory('common')
  constructor: ->
    return {

      checkbox: (name) ->
        if localStorage.getItem(name) isnt undefined
          initial_value = localStorage.getItem(name) is "true"

        ret = 
          type: 'checkbox'
          name: name
          value: initial_value

        return ret

      radio: (name, answers...) ->
          default_answers = 
            "yes": "yes"
            "no" : "no"

          if localStorage.getItem(name) isnt undefined
            initial_value = localStorage.getItem(name)

          ret = 
            name: name
            type: 'radio'
            value: initial_value
            answers: default_answers

          return ret
    }

