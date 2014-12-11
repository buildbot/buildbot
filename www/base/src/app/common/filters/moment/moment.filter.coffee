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
            mins = d.minutes()
            if mins < 10
                mins = '0' + mins
            secs = d.seconds()
            if secs < 10
                secs = '0' + secs
            if d.hours()
                return "#{d.hours()}:#{mins}:#{secs}"
            else if d.minutes()
                return "#{d.minutes()}:#{secs}"
            else
                return "#{d.seconds()}s"

class Dateformat extends Filter('common')
    constructor: (MOMENT) ->
        return (time, f) ->
            return MOMENT.unix(time).format(f)
