define(['jquery', 'realtimePages', 'helpers', 'popup', 'handlebars', 'mustache', 'text!templates/build.handlebars', 'text!templates/builders.mustache'], function ($, realtimePages, helpers, popup, hb, mustache, build, builders) {
    "use strict";
    var rtBuildDetail;
    var stepList = $('#stepList').find('> li');
    var buildHandle = Handlebars.compile(build);
    var isLoaded = false;
    var timerCreated = false;
    var noMoreReloads = false;

    //Global helper for Handlebar
    //TODO: Move this when it's used by more pages
    Handlebars.registerHelper('buildCSSClass', function(value) {
        return helpers.getCssClassFromStatus(value);
    });

    rtBuildDetail = {
        init: function () {
            var realtimeFunctions = realtimePages.defaultRealtimeFunctions();
            realtimeFunctions["build"] = rtBuildDetail.processBuildDetailPage;
            realtimePages.initRealtime(realtimeFunctions);
        }, processBuildDetailPage: function (data) {

            //We get slighlty different data objects from autobahn
            var keys = Object.keys(data);
            if (keys.length == 1) {
                data = data[keys[0]];
            }

            var buildStartTime = data["times"][0];
            var buildEndTime = data["times"][1];
            var buildFinished = (buildEndTime !== null);

            var eta = data["eta"];

            rtBuildDetail.refreshIfRequired(buildFinished);

            //Process Page
            rtBuildDetail.processBuildResult(data, buildStartTime, eta, buildFinished);
            rtBuildDetail.processSteps(data);
            helpers.summaryArtifactTests();

            //If build is running
            if (buildEndTime === null) {

                //Elapsed Time & Progress Bar
                if (timerCreated == false) {
                    helpers.startCounter($('#elapsedTimeJs'), buildStartTime);
                    timerCreated = true;
                }
            }
        },
        processBuildResult: function(data, startTime, eta, buildFinished) {
            var $buildResult = $('#buildResult');
            var progressBar = "";
            if (eta != 0) {
                progressBar = mustache.render(builders,
                    {progressBar: true, etaStart: startTime, etaCurrent: eta});
            }

            var props = {
                buildResults: true,
                b: data,
                buildIsFinished: buildFinished,
                progressBar: progressBar
            };

            var html = buildHandle(props);
            $buildResult.html(html);

            var $progressBar = $buildResult.find(".percent-outer-js");
            $progressBar.addClass("build-detail-progress");
            helpers.delegateToProgressBar($progressBar);
        },
        processSteps: function(data) {
            var html = "";
            var $stepList = $('#stepList');
            $.each(data["steps"], function (i, stepData) {
                var started = stepData['isStarted'];
                var finished = stepData['isFinished'];

                var status = stepData["results"][0];
                if (!started) {
                      status = 8;
                }
                else if (started && !finished) {
                    status = 7;
                }

                var cssClass = helpers.getCssClassFromStatus(status);
                var startTime = stepData.times[0];
                var endTime = stepData.times[1];
                var runTime = helpers.getTime(startTime, endTime);
                var props = {
                    step: true,
                    index: i,
                    stepStarted: stepData['isStarted'],
                    run_time: runTime,
                    css_class: cssClass,
                    s: stepData,
                    url: stepData['url']
                };
                html += buildHandle(props);
            });

            $stepList.html(html);
        },
        refreshIfRequired: function(buildFinished) {
            //Deal with page reload
            if (!noMoreReloads && isLoaded && buildFinished) {
                window.location = window.location + '#finished';
                window.location.reload();
            }
            if (noMoreReloads == false)
                noMoreReloads = buildFinished;

            isLoaded = true;
        }
    };

    return rtBuildDetail;
});