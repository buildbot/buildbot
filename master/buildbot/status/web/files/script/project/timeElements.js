define(["moment", "extend-moment"], function (moment, extendMoment) {
    "use strict";

    var HEARTBEAT = 5000,
        lastBeat,
        timeObjects = {"timeAgo": [], "elapsed": [], "progressBars": []},
        interval,
        oldLang = moment.lang(),
        lastCount = 0;

    var timeElements = {
        init: function () {
            if (interval === undefined) {
                timeElements._heartbeatInterval();
            }
        },
        _heartbeatInterval: function () {
            clearTimeout(interval);
            interval = setTimeout(timeElements._heartbeat, HEARTBEAT);
        },
        _heartbeat: function (force) {
            var now = new Date();
            // Process all of the time elements
            if (force === true || ((now - lastBeat) >= HEARTBEAT)) {
                var count = 0;
                $.each(timeObjects.timeAgo, function (i, obj) {
                    timeElements.processTimeAgo(obj.el, obj.time);
                    count++;
                });
                $.each(timeObjects.elapsed, function (i, obj) {
                    timeElements.processElapsed(obj.el, obj.time);
                    count++;
                });
                $.each(timeObjects.progressBars, function (i, obj) {
                    if (lastBeat !== undefined && obj.eta != 0) {
                        var diff = now - lastBeat;
                        obj.eta -= diff / 1000;
                    }
                    timeElements.processProgressBars(obj.el, obj.time, obj.eta);
                    count++;
                });
                lastBeat = now;
            }

            lastCount = count;

            if (interval !== undefined) {
                timeElements._heartbeatInterval();
            }
        },
        _addElem: function (el, obj, array) {
            if (el.length) {
                if ($(el).attr("data-timeElem") === undefined) {
                    $(el).attr("data-timeElem", "true");
                    array.push(obj);
                }
            }
        },
        addTimeAgoElem: function (el, startTimestamp) {
            var $el = $(el);
            var obj = {
                "el": $el,
                "time": parseInt(startTimestamp)
            };
            timeElements._addElem($el, obj, timeObjects.timeAgo);
        },
        addElapsedElem: function (el, startTimestamp) {
            var $el = $(el);
            var obj = {
                "el": $el,
                "time": parseInt(startTimestamp)
            };
            timeElements._addElem($el, obj, timeObjects.elapsed);
        },
        addProgressBarElem: function (el, startTimestamp, eta) {
            var $el = $(el);
            var obj = {
                "el": $el,
                "time": parseInt(startTimestamp),
                "eta": eta
            };
            timeElements._addElem($el, obj, timeObjects.progressBars);
        },
        updateTimeObjects: function () {
            timeElements._heartbeat(true);
        },
        clearTimeObjects: function (parentElem) {
            if (parentElem !== undefined) {
                var childElems = $(parentElem).find("[data-timeElem]");

                //Find elements that are in the given parentElem and remove them
                $.each(timeObjects, function (i, arr) {
                    timeObjects[i] = $.grep(arr, function (obj) {

                        //Is our parent element one of the parents of this elem?
                        var inParent = false;
                        if ($.contains(document.documentElement, obj.el[0])) {
                            $.each(childElems, function (x, c) {
                                if ($(c).is(obj.el)) {
                                    inParent = true;
                                    return false;
                                }
                                return true;
                            });
                            return inParent;
                        }
                        else {
                            //Remove elements not in the DOM
                            return true;
                        }
                    }, true);
                });
            }
            else {
                $.each(timeObjects, function (i) {
                    timeObjects[i] = [];
                });
            }
        },
        processTimeAgo: function ($el, startTimestamp) {
            $el.html(moment.unix(startTimestamp).fromServerNow());
        },
        processElapsed: function ($el, startTimestamp) {
            var now = extendMoment.getServerTime().unix(),
                time = now - startTimestamp;

            moment.lang('waiting-en');
            $el.html(moment.duration(time, 'seconds').humanize(true));
            moment.lang(oldLang);
        },
        processProgressBars: function ($el, startTime, etaTime) {
            var serverOffset = extendMoment.getServerOffset(),
                start = moment.unix(startTime),
                percentInner = $el.children('.percent-inner-js'),
                timeTxt = $el.children('.time-txt-js'),
                hasETA = etaTime != 0,
                percent = 100;

            if (hasETA) {
                var now = moment() + serverOffset,
                    etaEpoch = now + (etaTime * 1000.0),
                    overtime = etaTime < 0,
                    then = moment().add('s', etaTime) + serverOffset;

                percent = 100 - (then - now) / (then - start) * 100;
                percent = percent.clamp(0, 100);

                moment.lang('progress-bar-en');
                timeTxt.html(moment(etaEpoch).fromServerNow());

                if (overtime)
                    $el.addClass('overtime');

            }
            else {
                moment.lang('progress-bar-no-eta-en');
                timeTxt.html(moment(parseInt(startTime * 1000)).fromServerNow());
            }

            //Reset language to original
            moment.lang(oldLang);
            percentInner.css('width', percent + "%");
        },
        setHeartbeat: function (interval) {
            HEARTBEAT = interval;
            timeElements._heartbeatInterval();
        }
    };

    return timeElements;
});