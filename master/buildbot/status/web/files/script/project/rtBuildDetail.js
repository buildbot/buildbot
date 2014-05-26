/*global Handlebars */
define(['jquery', 'realtimePages', 'helpers', 'popup', 'handlebars', 'mustache', 'text!templates/build.handlebars', 'text!templates/builders.mustache', 'timeElements'], function ($, realtimePages, helpers, popup, hb, mustache, build, builders, timeElements) {
    "use strict";
    var rtBuildDetail,
        stepList = $('#stepList').find('> li'),
        buildHandle = Handlebars.compile(build),
        isLoaded = false,
        noMoreReloads = false;

    //Global helper for Handlebar
    //TODO: Move this when it's used by more pages
    Handlebars.registerHelper('buildCSSClass', function (value) {
        return helpers.getCssClassFromStatus(value);
    });

    rtBuildDetail = {
        init: function () {
            var realtimeFunctions = realtimePages.defaultRealtimeFunctions();
            realtimeFunctions.build = rtBuildDetail.processBuildDetailPage;
            realtimePages.initRealtime(realtimeFunctions);
            timeElements.setHeartbeat(1000);

            // insert codebase and branch on the builders page
            if (window.location.search !== '') {
                // Parse the url and insert current codebases and branches
                var $dtWTop = $('.top');
                helpers.codeBaseBranchOverview($dtWTop);
            }
        },
        processBuildDetailPage: function (data) {
            //We get slighlty different data objects from autobahn
            var keys = Object.keys(data);
            if (keys.length === 1) {
                data = data[keys[0]];
            }

            var buildStartTime = data.times[0],
                buildEndTime = data.times[1],
                buildFinished = (buildEndTime !== null),
                eta = data.eta;

            rtBuildDetail.refreshIfRequired(buildFinished);

            //Process Page
            rtBuildDetail.processBuildResult(data, buildStartTime, eta, buildFinished);
            rtBuildDetail.processSteps(data);
            helpers.summaryArtifactTests();

            //If build is running
            if (buildEndTime === null) {
                //Elapsed Time & Progress Bar
                timeElements.addElapsedElem($('#elapsedTimeJs'), buildStartTime);
            }

            timeElements.updateTimeObjects();
        },
        processBuildResult: function(data, startTime, eta, buildFinished) {
            var $buildResult = $('#buildResult');
            timeElements.clearTimeObjects($buildResult);
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
        processSteps: function (data) {
            var html = "";
            var $stepList = $('#stepList');
            var count = 1;
            $.each(data.steps, function (i, stepData) {
                if (stepData.hidden) {
                    return true;
                }

                var started = stepData.isStarted;
                var finished = stepData.isFinished;

                var status = stepData.results[0];
                if (!started) {
                    status = 9;
                } else if (started && !finished) {
                    status = 8;
                }

                var cssClass = helpers.getCssClassFromStatus(status);
                var startTime = stepData.times[0];
                var endTime = stepData.times[1];
                var runTime = helpers.getTime(startTime, endTime);
                var props = {
                    step: true,
                    index: count,
                    stepStarted: stepData['isStarted'],
                    run_time: runTime,
                    css_class: cssClass,
                    s: stepData,
                    url: stepData.url
                };
                html += buildHandle(props);
                count += 1;

                return true;
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