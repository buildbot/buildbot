class Timeago extends Filter('common')
    constructor: (MOMENT) ->
        return (time) ->
            return MOMENT.unix(time).fromNow()

class Duration extends Filter('common')
    constructor: (MOMENT) ->
        return (time) ->
            return MOMENT.unix(time).from(MOMENT.unix(0),1)

class Durationformat extends Filter('common')
    constructor: (MOMENT) ->
        return (time) ->
            d = MOMENT.duration(time * 1000)
            if d.hours()
                return "#{d.hours()}:#{d.minutes()}:#{d.seconds()}"
            else if d.minutes()
                return "#{d.minutes()}:#{d.seconds()}"
            else
                return "#{d.seconds()}s"

class Dateformat extends Filter('common')
    constructor: (MOMENT) ->
        return (time, f) ->
            return MOMENT.unix(time).format(f)