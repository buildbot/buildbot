class Waterfall extends Config
    constructor: (bbSettingsServiceProvider) ->

        bbSettingsServiceProvider.addSettingsGroup
            name: 'Waterfall'
            caption: 'Waterfall related settings'
            items: [
                type: 'integer'
                name: 'scaling_waterfall'
                caption: 'Scaling factor'
                default_value: 1
            ,
                type: 'integer'
                name: 'min_column_width_waterfall'
                caption: 'Minimum column width (px)'
                default_value: 40
            ,
                type: 'integer'
                name: 'lazy_limit_waterfall'
                caption: 'Lazy loading limit'
                default_value: 40
            ,
                type: 'integer'
                name: 'idle_threshold_waterfall'
                caption: 'Idle time threshold in unix time stamp (eg. 300 = 5 min)'
                default_value: 300
            ,
                type: 'bool'
                name: 'number_background_waterfall'
                caption: 'Build number background'
                default_value: false
            ]
