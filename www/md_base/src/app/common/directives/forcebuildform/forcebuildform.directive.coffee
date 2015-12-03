class ForcebuildForm extends Directive

    constructor: ->
        return {
            restrict: 'E'
            controller: '_ForcebuildFormController'
            controllerAs: 'form'
            bindToController: true
            scope:
                model: '='
                fields: '='
                errors: '='
        }

class _ForcebuildForm extends Controller

    constructor: ($scope, $element, $compile) ->
        elem = $compile(@buildfields())($scope)
        $element.append elem

    element: (tag, attributes) ->
        elem = angular.element("<#{tag}></#{tag}>")
        elem.attr(attributes) if attributes
        return elem

    labelElement: (text) ->
        text = text.trim().replace /:$/, ''
        return null if not text
        label = @element 'label'
        label.text(text)
        return label

    buildfields: ->
        elem = @element 'div', class: 'inner'
        for field in @fields
            elem.append @buildfield(field)
        return elem

    buildfield: (field) ->
        if field.type == 'nested'
            # Build layout
            switch field.layout
                when 'vertical'
                    return @verticalLayout(field)
                when 'tab'
                    return @tabLayout(field)
                else
                    return @simpleLayout(field)
        else
            # Build normal fields
            switch field.type
                when 'textarea'
                    return @textareaField(field)
                when 'int'
                    return @intField(field)
                when 'list'
                    return @listField(field)
                when 'bool'
                    return @boolField(field)
                else
                    return @textField(field)

    verticalLayout: (field) ->
        layout = if field.columns > 1 then 'row' else 'column'
        elem = @element 'div',
            'class': 'vertical-layout'
            'layout-gt-md': layout
            'layout-wrap': 'layout-wrap'
        flex = 'flex'
        flex = '50' if field.columns == 2
        flex = '33' if field.columns == 3
        for subfield in field.fields
            f = @buildfield(subfield)
            f.attr {flex: 'flex', 'flex-gt-md': flex}
            elem.append f
        return elem

    tabLayout: (field) ->
        elem = @element 'div', class: 'tab-layout'
        tabs = @element 'md-tabs',
            'md-dynamic-height': 'md-dynamic-height'
            'md-border-bottom': 'md-border-bottom'

        for f in field.fields
            tab = @element 'md-tab', label: f.label
            tab.append @buildfield(f)
            tabs.append tab

        elem.append tabs
        return elem

    simpleLayout: (field) ->
        elem = @element 'div', class: 'simple-layout'
        elem.append(@buildfield(f)) for f in field.fields
        return elem

    textField: (field) ->
        elem = @element 'div', class: 'text-field field'
        container = @element 'md-input-container'
        input = @element 'input',
            'required': field.required
            'ng-model': "form.model.#{ field.name }"
            'md-is-error': "form.errors.#{ field.name }"
        container.append @labelElement field.label
        container.append input
        elem.append container
        return elem

    textareaField: (field) ->
        elem = @element 'div', class: 'textarea-field field'
        container = @element 'md-input-container'
        textarea = @element 'textarea',
            'required': field.required
            'ng-model': "form.model.#{ field.name }"
            'md-is-error': "form.errors.#{ field.name }"
        container.append @labelElement field.label
        container.append textarea
        elem.append container
        return elem

    intField: (field) ->
        elem = @element 'div', class: 'int-field field'
        container = @element 'md-input-container'
        input = @element 'input',
            'type': 'number'
            'required': field.required
            'ng-model': "form.model.#{ field.name }"
            'md-is-error': "form.errors.#{ field.name }"
        container.append @labelElement field.label
        container.append input
        elem.append container
        return elem

    boolField: (field) ->
        elem = @element 'div', class: 'bool-field field'
        checkbox = @element 'md-checkbox',
            'ng-model': "form.model.#{ field.name }"
            'md-is-error': "form.errors.#{ field.name }"
        chechbox.text field.label.trim().replace /:$/, ''
        elem.append checkbox
        return elem

    listField: (field) ->
        elem = @element 'div', class: 'list-field field'
        container = @element 'md-input-container'
        select = @element 'md-select',
            'required': field.required
            'ng-model': "form.model.#{ field.name }"
            'multiple': field.multiple
            'md-is-error': "form.errors.#{ field.name }"
        for choice in field.choices
            f = @element 'md-option', value: choice
            f.text(choice)
            select.append f
        container.append @labelElement field.label
        container.append select
        elem.append container
        return elem
