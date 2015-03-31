class Waterfall extends Config
    constructor: (bbSettingsServiceProvider) ->

        bbSettingsServiceProvider.addSettingsGroup
            name: 'Waterfall'
            caption: 'Waterfall related settings'
            items: [
                type: 'integer'
                name: 'margin_top_waterfall'
                caption: 'Margin top (px)'
                default_value: 15
            ,
                type: 'integer'
                name: 'margin_right_waterfall'
                caption: 'Margin right (px)'
                default_value: 20
            ,
                type: 'integer'
                name: 'margin_bottom_waterfall'
                caption: 'Margin bottom (px)'
                default_value: 20
            ,
                type: 'integer'
                name: 'margin_left_waterfall'
                caption: 'Margin left (px)'
                default_value: 70
            ,
                type: 'integer'
                name: 'gap_waterfall'
                caption: 'Gap between groups (px)'
                default_value: 30
            ,
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
