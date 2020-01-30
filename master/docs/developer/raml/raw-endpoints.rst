Raw endpoints
.............

.. jinja:: data_api

    Raw endpoints allow to download content in their raw format (i.e. not within a json glue).
    The ``content-disposition`` http header is set, so that the browser knows which file to store the content to.

    {% for ep, config in raml.rawendpoints.items()|sort %}

    .. bb:rpath:: {{ep}}

        {% for key, value in config.uriParameters.items() -%}
            :pathkey {{value.type}} {{key}}: {{raml.reindent(value.description, 4*2)}}
        {% endfor %}

    {{config['get'].description}}

    {% endfor %}
