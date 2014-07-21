/*global define*/
define(["jquery", "moment", "extend-moment"], function ($, moment, extendMoment) {
    "use strict";

    var HEARTBEAT = 5000,
        ANIM_INTERVAL = 80,
        lastAnim = 0,
        lastBeat,
        timeObjects = {"timeAgo": [], "elapsed": [], "progressBars": []},
        interval,
        oldLang = moment.lang(),
        animPos = 0;

    var privateFunc = {
        heartbeatInterval: function () {
            clearTimeout(interval);
            interval = setTimeout(privateFunc.heartbeat, HEARTBEAT);
        },
        heartbeat: function (force) {
            var now = new Date();

            // Process all of the time elements
            if (force === true || ((now - lastBeat) > HEARTBEAT)) {
                $.each(timeObjects.timeAgo, function (i, obj) {
                    privateFunc.processTimeAgo(obj.el, obj.time);
                });
                $.each(timeObjects.elapsed, function (i, obj) {
                    privateFunc.processElapsed(obj.el, obj.time);
                });
                $.each(timeObjects.progressBars, function (i, obj) {
                    if (lastBeat !== undefined && obj.eta !== 0) {
                        var diff = now - lastBeat;
                        obj.eta -= diff / 1000;
                    }
                    privateFunc.processProgressBars(obj.el, obj.time, obj.eta);
                });
                lastBeat = now;
            }

            privateFunc.heartbeatInterval();
        },
        addElem: function (el, obj, array) {
            if (el.length) {
                if ($(el).attr("data-timeElem") === undefined) {
                    $(el).attr("data-timeElem", "true");
                    array.push(obj);
                }
            }
        },
        spinIconAnimation: function (ts) {
            var frames = 10;
            var frameWidth = 13;
            $.each($('.animate-spin'), function (i, obj) {
                var $obj = $(obj);
                if (animPos >= frames) {
                    animPos = 0;
                }

                var offset = animPos * -frameWidth;
                $obj.css("background-position", offset + "px 0px");
            });

            if ((ts - lastAnim) > ANIM_INTERVAL) {
                animPos += 1;
                lastAnim = ts;
            }

            window.requestAnimationFrame(privateFunc.spinIconAnimation);
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
                start = moment.unix(startTime).startOf('second'),
                startUnix = start.unix().toFixed(2),
                percentInner = $el.children('.percent-inner-js'),
                timeTxt = $el.children('.time-txt-js'),
                hasETA = etaTime !== 0,
                percent = 100;

            if (hasETA) {
                var now = moment().add('ms', serverOffset).startOf('second').unix().toFixed(2),
                    etaEpoch = moment().add('s', etaTime).add('ms', serverOffset).startOf('second'),
                    then = etaEpoch.unix().toFixed(2),
                    overtime = moment(etaEpoch).diff() < 0;

                percent = Math.floor(100 - (then - now) / (then - startUnix) * 100);
                percent = percent.clamp(0, 100);

                moment.lang('progress-bar-en');
                timeTxt.html(moment(etaEpoch).fromServerNow());

                if (overtime) {
                    $el.addClass('overtime');
                }

            } else {
                moment.lang('progress-bar-no-eta-en');
                timeTxt.html(start.fromServerNow());
            }

            //Reset language to original
            moment.lang(oldLang);
            percentInner.css('width', percent + "%");
        }
    };

    return {
        init: function () {
            if (interval === undefined) {
                privateFunc.heartbeatInterval();
                extendMoment.init();
            }
            window.requestAnimationFrame(privateFunc.spinIconAnimation);
        },
        addTimeAgoElem: function (el, startTimestamp) {
            var $el = $(el);
            var obj = {
                "el": $el,
                "time": parseInt(startTimestamp, 10)
            };
            privateFunc.addElem($el, obj, timeObjects.timeAgo);
        },
        addElapsedElem: function (el, startTimestamp) {
            var $el = $(el);
            var obj = {
                "el": $el,
                "time": parseInt(startTimestamp, 10)
            };
            privateFunc.addElem($el, obj, timeObjects.elapsed);
        },
        addProgressBarElem: function (el, startTimestamp, eta) {
            var $el = $(el);
            var obj = {
                "el": $el,
                "time": parseInt(startTimestamp, 10),
                "eta": parseInt(eta, 10)
            };

            if (isNaN(obj.eta)) {
                obj.eta = 0;
            }

            privateFunc.addElem($el, obj, timeObjects.progressBars);
        },
        updateTimeObjects: function () {
            privateFunc.heartbeat(true);
        },
        clearTimeObjects: function (parentElem) {
            if (parentElem !== undefined) {
                var childElems = $(parentElem).find("[data-timeelem]");

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

                        //Remove elements not in the DOM
                        return true;

                    }, true);
                });
            } else {
                $.each(timeObjects, function (i) {
                    timeObjects[i] = [];
                });
            }
        },
        setHeartbeat: function (interval) {
            HEARTBEAT = interval;
            privateFunc.heartbeatInterval();
        },
        _timeObjects: timeObjects
    };
});
