class Timeago
    constructor: (MOMENT) ->
        return (time) ->
            return MOMENT.unix(time).fromNow()

class Duration
    constructor: (MOMENT) ->
        return (time) ->
            return MOMENT.unix(time).from(MOMENT.unix(0),1)

class Durationformat
    constructor: (MOMENT) ->
        return (time) ->
            d = MOMENT.duration(time * 1000)
            m = MOMENT.utc(d.asMilliseconds())
            days = Math.floor(d.asDays())
            if days
                plural = ""
                if days > 1
                    plural = "s"
                return "#{days} day#{plural} " + m.format('H:mm:ss')
            if d.hours()
                return m.format('H:mm:ss')
            if d.minutes()
                return m.format('m:ss')
            else
                return m.format('s') + " s"

class Dateformat
    constructor: (MOMENT) ->
        return (time, f) ->
            return MOMENT.unix(time).format(f)


angular.module('common')
.filter('timeago', ['MOMENT', Timeago])
.filter('duration', ['MOMENT', Duration])
.filter('durationformat', ['MOMENT', Durationformat])
.filter('dateformat', ['MOMENT', Dateformat])