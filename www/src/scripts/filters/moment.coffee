angular.module('app').constant 'moment', window.moment
angular.module('app').filter 'timeago', ['moment', (moment) ->
    return (time) ->
        return moment.unix(time).fromNow()
]
angular.module('app').filter 'duration', ['moment', (moment) ->
    return (time) ->
        return moment.unix(time).from(moment.unix(0),1)
]
angular.module('app').filter 'durationformat', ['moment', (moment) ->
    return (time) ->
        d = moment.duration(time * 1000)
        if d.hours()
            return "#{d.hours()}:#{d.minutes()}:#{d.seconds()}"
        else if d.minutes()
            return "#{d.minutes()}:#{d.seconds()}"
        else
            return "#{d.seconds()}s"
]
angular.module('app').filter 'dateformat', ['moment', (moment) ->
    return (time, f) ->
        return moment.unix(time).format(f)
]