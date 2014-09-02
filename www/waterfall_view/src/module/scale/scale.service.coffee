class ScaleService extends Factory
    constructor: ->
        return class Service
            constructor: (@d3) ->

            # Returns x scale
            getX: (builders, width) ->
                @d3.scale.ordinal()
                    .domain(builders.map (builder) -> builder.builderid)
                    .rangeRoundBands([0, width], width / (builders.length * 400))

            # Returns y scale
            getY: (groups, gap, height) ->
                H = height;
                I = H - (groups.length - 1) * gap
                T = 0
                T += (group.max - group.min) for group in groups

                class Y

                    # date to coordinate
                    constructor: (date) ->
                        periods = []
                        for group, id in groups
                            if group.min <= date <= group.max
                                periods.push(date - group.min)
                                sum = 0
                                sum += period for period in periods
                                return H - (I / T) * sum - id * gap
                            else periods.push(group.max - group.min)
                        return undefined

                    # coordinate to date
                    @invert: (coordinate) ->
                        periods = []
                        for group, id in groups
                            sum = 0
                            sum += period for period in periods
                            date = (H - coordinate - id * gap) * (T / I) - sum + group.min
                            if group.min <= date <= group.max
                                return date
                            periods.push(group.max - group.min)
                        return undefined

            # Returns an id to name scale
            getBuilderName: (builders) ->
                @d3.scale.ordinal()
                    .domain(builders.map (builder) -> builder.builderid)
                    .range(builders.map (builder) -> builder.name)
