/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS205: Consider reworking code to avoid use of IIFEs
 * DS206: Consider reworking classes to avoid initClass
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */

import 'angular-animate';
import '@uirouter/angularjs';
import 'guanlecoja-ui';
import 'buildbot-data-js';
import _ from 'lodash';

var WaterfallController = (function() {
    let self = undefined;
    let Cls = class Waterfall {
        static initClass() {
            self = null;

            // Y axis tick values
            this.prototype.ticks = [];
        }
        constructor($rootElement, $scope, $q, $timeout, $window, $log,
                      $uibModal, dataService, d3Service, dataProcessorService,
                      scaleService, bbSettingsService, glTopbarContextualActionsService,
                      $location, $rootScope) {
            this.zoomPlus = this.zoomPlus.bind(this);
            this.zoomMinus = this.zoomMinus.bind(this);
            this.renderNewData = this.renderNewData.bind(this);
            this.$rootElement = $rootElement;
            this.$scope = $scope;
            this.$window = $window;
            this.$log = $log;
            this.$uibModal = $uibModal;
            this.$location = $location;
            this.$rootScope = $rootScope;
            this.$scope.tags_filter = this.tags_filter = [];
            this.dataProcessorService = dataProcessorService;
            this.bbSettingsService = bbSettingsService;
            self = this;
            const actions = [{
                caption: "",
                icon: "search-plus",
                action: this.zoomPlus
            }
            , {
                caption: "",
                icon: "search-minus",
                action: this.zoomMinus
            }
            ];

            // 'waterfall' class needs to be dynamically added to the body in order
            //  to support waterfall-specific styling of the body.  (this is a bit
            //  awkward since the body is provided by guanlecoja-ui and is the same
            //  element as you switch between different plugin pages, therefore the
            //  class needs to removed upon exiting the waterfall via the $destroy
            //  event below.)
            const body = this.$rootElement.find("body");
            body.addClass("hundredpercent");
            this.$scope.$on("$destroy", ()=> {
                return body.removeClass("hundredpercent");
            });

            glTopbarContextualActionsService.setContextualActions(actions);

            // Clear contextual action buttons on destroy
            const clearGl = function () {
                glTopbarContextualActionsService.setContextualActions([]);
            };
            $scope.$on('$destroy', clearGl);

            // Show the loading spinner
            this.loading = true;
            this.dataAccessor = dataService.open().closeOnDestroy(this.$scope);
            // Get Waterfall settings
            this.s = this.bbSettingsService.getSettingsGroup('Waterfall');
            this.c = {
                // Margins around the chart
                margin: {
                    top: 15,
                    right: 20,
                    bottom: 20,
                    left: 70
                },

                // Gap between groups (px)
                gap: 30,

                // Default vertical scaling
                scaling: this.s.scaling_waterfall.value,

                // Minimum builder column width (px)
                minColumnWidth: this.s.min_column_width_waterfall.value,

                // Y axis time format (new line: ^)
                timeFormat: '%x^%H:%M',

                // Lazy load limit
                limit: this.s.lazy_limit_waterfall.value,

                // Idle time threshold in unix time stamp (eg. 300 = 5 min)
                threshold: this.s.idle_threshold_waterfall.value,

                // Grey rectangle below buildids
                buildidBackground: this.s.number_background_waterfall.value
            };

            // Load data (builds and builders)
            this.all_builders = this.dataAccessor.getBuilders({order: 'name'});
            this.$scope.builders = (this.builders = this.all_builders);
            this.buildLimit = this.c.limit;
            this.$scope.builds = (this.builds = this.dataAccessor.getBuilds({limit: this.buildLimit, order: '-started_at'}));
            this.$scope.masters = this.dataAccessor.getMasters();

            d3Service.get().then(d3 => {

                // Create a scale object
                this.d3 = d3;
                this.scale = new scaleService(this.d3);

                // Create groups and add builds to builders
                this.groups = this.dataProcessorService.getGroups(this.all_builders, this.builds, this.c.threshold);
                if (this.s.show_builders_without_builds.value) {
                    this.$scope.builders = this.all_builders;
                } else {
                    this.$scope.builders = (this.builders = this.dataProcessorService.filterBuilders(this.all_builders));
                }
                if (!this.s.show_old_builders.value) {
                    const ret = [];
                    for (let builder of this.$scope.builders) {
                        if (this.hasActiveMaster(builder)) {
                            ret.push(builder);
                        }
                    }
                    this.$scope.builders = this.builders = ret;
                }
                // Add builder status to builders
                this.dataProcessorService.addStatus(this.builders);

                // Select containers
                this.waterfall = this.d3.select('.waterfall');
                this.container = this.waterfall.select('.svg-container');
                this.header = this.waterfall.select('.header-content');
                // Append svg elements to the containers
                this.createElements();

                // Render the waterfall
                this.render();
                // Hide the spinner
                this.loading = false;

                // Render on resize
                this.$scope.$watch(
                    () => this.waterfall.style('width')
                ,
                    (n, o) => { if (n !== o) { this.render(); } }
                , true
                );

                // Update view on data change
                this.loadingMore = false;
                this.$scope.masters.onChange = this.renderNewData;
                this.builds.onChange = (this.all_builders.onChange = this.renderNewData);


                // Lazy load builds on scroll
                const containerParent = this.container.node().parentNode;
                const onScroll = () => {
                    if (!this.loadingMore && ((this.getHeight() - containerParent.scrollTop) < 1000)) {
                        this.loadingMore = true;
                        return this.loadMore();
                    }
                };

                // Bind scroll event listener
                angular.element(containerParent).bind('scroll', onScroll);

                const resizeHandler = () => this.render();
                const window = angular.element(this.$window);
                window.bind('resize', resizeHandler);
                const keyHandler =  e => {
                    // +
                    if (e.key === '+') {
                        e.preventDefault();
                        this.zoomPlus();
                    }
                    // -
                    if (e.key === '-') {
                        e.preventDefault();
                        return this.zoomMinus();
                    }
                };
                window.bind('keypress', keyHandler);
                this.$scope.$on('$destroy', function() {
                    window.unbind('keypress', keyHandler);
                    return window.unbind('resize', resizeHandler);
                });
            });

            $rootScope.$on('$locationChangeSuccess', function() {
                self.renderNewData(self.$scope.tags_filter);
            });
        }

        hasActiveMaster(builder) {
            let active = false;
            if ((builder.masterids == null)) {
                return false;
            }
            for (let mid of Array.from(builder.masterids)) {
                const m = this.$scope.masters.get(mid);
                if ((m != null) && m.active) {
                    active = true;
                }
            }
            if (builder.tags.includes('_virtual_')) {
                active = true;
            }
            return active;
        }


        zoomPlus() {
            this.incrementScaleFactor();
            this.render();
        }

        zoomMinus() {
            this.decrementScaleFactor();
            this.render();
        }
        /*
         * Increment and decrement the scale factor
         */
        incrementScaleFactor() {
            this.c.scaling *= 1.5;
            this.s.scaling_waterfall.value *= 1.5;
            return this.bbSettingsService.save();
        }

        decrementScaleFactor() {
            this.c.scaling /= 1.5;
            this.s.scaling_waterfall.value /= 1.5;
            return this.bbSettingsService.save();
        }

        /*
         * Load more builds
         */
        loadMore() {
            if (this.builds.length < this.buildLimit) {
                // last query returned less build than expected, so we went to the beginning of time
                // no need to query again
                return;
            }
            this.buildLimit = this.builds.length + this.c.limit;
            const builds = this.dataAccessor.getBuilds({limit: this.buildLimit, order: '-started_at'});
            builds.onChange = builds => {
                this.builds.close();  // force close the old collection's auto-update
                this.builds = builds;
                // renders the new data
                builds.onChange = this.renderNewData;
                builds.onChange();
            };
        }

        /*
         * Create svg elements for chart and header, append svg groups
         */
        createElements() {

            // Remove any unwanted elements first
            this.container.selectAll('*').remove();
            this.header.selectAll('*').remove();

            this.chart = this.container.append('svg')
                .append('g')
                    .attr('transform', `translate(${this.c.margin.left}, ${this.c.margin.top})`)
                    .attr('class', 'chart');

            const height = this.getHeaderHeight();
            this.waterfall.select(".header").style("height", height);
            return this.header = this.header.append('svg')
                .append('g')
                    .attr('transform', `translate(${this.c.margin.left}, ${height})`)
                    .attr('class', 'header');
        }
        /*
         * Get the container width
         */
        getWidth() { return parseInt(this.container.style('width').replace('px', ''), 10); }

        /*
         * Set the content width
         */
        setWidth() {
            if (this.c.minColumnWidth > 0) {
                const columnWidth = (this.$window.innerWidth - this.c.margin.right - this.c.margin.left) / this.builders.length;

                const wider = this.c.minColumnWidth <= columnWidth;

                const width =
                    wider ? '100%'
                    :
                        `${(this.builders.length * this.c.minColumnWidth) + this.c.margin.right + this.c.margin.left}px`;

                this.waterfall.select('.inner-content').style('width', width);
                return this.waterfall.select('.header-content').style('width', width);

            } else {
                return this.$log.error(`Bad column width configuration\n\t min: ${this.c.minColumnWidth}`);
            }
        }

        /*
         * Get the container height
         */
        getHeight() { return parseInt(this.container.style('height').replace('px', ''), 10); }

        /*
         * Set the container height
         */
        setHeight() {
            let h = -this.c.gap;
            for (let group of Array.from(this.groups)) {
                h += ((group.max - group.min) + this.c.gap);
            }
            let height = (h * this.c.scaling) + this.c.margin.top + this.c.margin.bottom;
            if (height < parseInt(this.waterfall.style('height').replace('px', ''), 10)) {
                this.loadMore();
            }
            this.container.style('height', `${height}px`);
            height = this.getHeaderHeight();
            this.waterfall.select("div.header").style("height", height + "px");
            return this.header.attr('transform', `translate(${this.c.margin.left}, ${height})`);
        }

        /*
         * Returns content width
         */
        getInnerWidth() {
            const width = this.getWidth();
            return width - this.c.margin.left - this.c.margin.right;
        }

        /*
         * Returns content height
         */
        getInnerHeight() {
            const height = this.getHeight();
            return height - this.c.margin.top - this.c.margin.bottom;
        }

        /*
         * Returns headers height
         */
        getHeaderHeight() {
            let max_buildername = 0;
            for (let builder of Array.from(this.builders)) {
                max_buildername = Math.max(builder.name.length, max_buildername);
            }
            return Math.max(100, max_buildername * 3);
        }

        /*
         * Returns the result string of a builder, build or step
         */
        getResultClassFromThing(b) {
            let result;
            if (!b.complete && (b.started_at >= 0)) {
                result = 'pending';
            } else {
                switch (b.results) {
                    case 0: result = 'success'; break;
                    case 1: result = 'warnings'; break;
                    case 2: result = 'failure'; break;
                    case 3: result = 'skipped'; break;
                    case 4: result = 'exception'; break;
                    case 5: result = 'cancelled'; break;
                    default: result = 'unknown';
                }
            }
            return result;
        }

        /*
         * Draw x axis
         */
        drawXAxis() {
            const x = this.scale.getX(this.builders, this.getInnerWidth());
            const builderName = this.scale.getBuilderName(this.builders);

            // Remove old axis
            this.header.select('.axis.x').remove();
            // Select axis
            const axis = this.header.append('g')
                .attr('class', 'axis x');

            // Remove previous elements
            axis.selectAll('*').remove();

            // Top axis shows builder names
            const xAxis = this.d3.svg.axis()
                .scale(x)
                .orient('top')
                .tickFormat(builderName);

            const xAxisSelect = axis.call(xAxis);

            // Add link
            const link = function(builderid) {
                const p = self.d3.select(this.parentNode);
                const a = p.append('a')
                    .attr('xlink:href', `#/builders/${builderid}`);
                return a.node().appendChild(this);
            };

            // Rotate text
            xAxisSelect.selectAll('text')
                .style('text-anchor', 'start')
                .attr('transform', 'translate(0, -16) rotate(-25)')
                .attr('dy', '0.75em')
                .each(link);

            // Rotate tick lines
            return xAxisSelect.selectAll('line')
                .data(this.builders)
                .attr('transform', 'rotate(90)')
                .attr('x1', 0)
                .attr('x2', 0)
                .attr('y1', x.rangeBand(1) / 2)
                .attr('y2', -x.rangeBand(1) / 2)
                .attr('class', self.getResultClassFromThing)
                .classed('stroke', true);
        }
        addTicks(build) {
            const y = this.scale.getY(this.groups, this.c.gap, this.getInnerHeight());
            return this.ticks = this.ticks.concat([y.getCoord(build.complete_at),
                                                   y.getCoord(build.started_at)]);
        }
        removeTicks() { return this.ticks = []; }

        /*
         * Draw y axis
         */
        drawYAxis() {
            let i = this.d3.scale.linear();
            const y = this.scale.getY(this.groups, this.c.gap, this.getInnerHeight());

            // Remove old axis
            this.chart.select('.axis.y').remove();
            const axis = this.chart.append('g')
                .attr('class', 'axis y');

            // Stay on left on horizontal scrolling
            axis.attr('transform', `translate(${this.waterfall.node().scrollLeft}, 0)`);
            this.waterfall.on('scroll', function() {  return yAxis.attr('transform', `translate(${this.scrollLeft}, 0)`); });

            // White background
            axis.append('rect')
                .attr('x', -this.c.margin.left)
                .attr('y', -this.c.margin.top)
                .attr('width', this.c.margin.left)
                .attr('height', this.getHeight())
                .style('fill', '#fff');

            let { ticks } = this;
            for (let group of Array.from(this.groups)) {
                ticks = ticks.concat([y.getCoord(group.min), y.getCoord(group.max)]);
            }

            // Y axis tick format
            const tickFormat = coordinate => {
                const timestamp = y.invert(coordinate);
                const date = new Date(timestamp * 1000);
                const format = this.d3.time.format(this.c.timeFormat);
                return format(date);
            };

            var yAxis = this.d3.svg.axis()
                .scale(i)
                .orient('left')
                .tickValues(ticks)
                .tickFormat(tickFormat);

            yAxis = axis.call(yAxis);

            // Break text on ^ character
            const lineBreak = function() {
                const e = self.d3.select(this);
                const words = e.text().split('^');
                e.text('');

                for (i = 0; i < words.length; i++) {
                    const word = words[i];
                    const text = e.append('tspan').text(word);
                    if (i !== 0) {
                        const x = e.attr('x');
                        text.attr('x', x).attr('dy', i * 10);
                    }
                }
            };
            yAxis.selectAll('text').each(lineBreak);

            const dasharray = tick => Array.from(this.ticks).includes(tick) ? '2, 5' : '2, 1';

            return yAxis.selectAll('.tick')
                .append('line')
                    .attr('x2', this.getInnerWidth())
                    .attr('stroke-dasharray', dasharray);
        }

        drawBuilds() {
            const x = this.scale.getX(this.builders, this.getInnerWidth());
            const y = this.scale.getY(this.groups, this.c.gap, this.getInnerHeight());

            // Remove previous elements
            this.chart.selectAll('.builder').remove();

            // Create builder columns
            const builders = this.chart.selectAll('.builder')
                .data(this.builders).enter()
                .append('g')
                    .attr('class', 'builder')
                    .attr('transform', builder => `translate(${x(builder.builderid)}, 0)`);

            // Create build group for each build
            const data = builder => builder.builds;
            const key = build => build.buildid;
            const builds = builders.selectAll('.build')
                .data(data, key).enter()
                .append('g')
                    .attr('class', 'build')
                    .attr('transform', build => `translate(0, ${y.getCoord(build.complete_at)})`);
            const max = function(a, b) {
                if (a > b) {
                    return a;
                }
                return b;
            };
            // Draw rectangle for each build
            const height = build => max(10, Math.abs(y.getCoord(build.started_at) -
                                                     y.getCoord(build.complete_at)));
            builds.append('rect')
                .attr('class', self.getResultClassFromThing)
                .attr('width', x.rangeBand(1))
                .attr('height', height)
                .classed('fill', true);

            // Optional: grey rectangle below buildids
            if (this.c.buildidBackground) {
                builds.append('rect')
                    .attr('y', -15)
                    .attr('width', x.rangeBand(1))
                    .attr('height', 15)
                    .style('fill', '#ccc');
            }

            // Draw text over builds
            builds.append('text')
                .attr('class', 'id')
                .attr('x', x.rangeBand(1) / 2)
                .attr('y', -3)
                .text(build => build.number);

            // Add event listeners
            return builds
                .on('mouseover', this.mouseOver)
                .on('mousemove', this.mouseMove)
                .on('mouseout', this.mouseOut)
                .on('click', this.click);
        }

        /*
         * Event actions
         */
        mouseOver(build) {
            const e = self.d3.select(this);
            const mouse = self.d3.mouse(this);
            self.addTicks(build);
            self.drawYAxis();

            // Move build and builder to front
            const p = self.d3.select(this.parentNode);
            this.parentNode.appendChild(this);
            p.each(function() { return this.parentNode.appendChild(this); });

            // Show tooltip on the left or on the right
            const r = build.builderid < (self.builders.length / 2);

            // Create tooltip
            let height = 40;
            const points = function() {
                if (r) { return `20,0 0,${height / 2} 20,${height} 170,${height} 170,0`;
                } else { return `150,0 170,${height / 2} 150,${height} 0,${height} 0,0`; }
            };
            const tooltip = e.append('g')
                .attr('class', 'svg-tooltip')
                .attr('transform', `translate(${mouse[0]}, ${mouse[1]})`)
                .append('g')
                    .attr('class', 'tooltip-content')
                    .attr('transform', `translate(${r ? 5 : -175}, ${- height / 2})`);

            tooltip.append('polygon')
                .attr('points', points());

            // Load steps
            build.loadSteps().onChange = function(buildsteps) {
                // Resize the tooltip
                height = (buildsteps.length * 15) + 7;
                tooltip.transition().duration(100)
                    .attr('transform', `translate(${r ? 5 : -175}, ${- height / 2})`)
                    .select('polygon')
                        .attr('points', points());

                const duration = function(step) {
                    const d = new Date((step.complete_at - step.started_at) * 1000);
                    if (d > 0) { return `(${d / 1000}s)`; } else { return ''; }
                };
                tooltip.selectAll('.buildstep')
                    .data(buildsteps)
                    .enter().append('g')
                    .attr('class', 'buildstep')
                    // Add text
                    .append('text')
                        .attr('y', (step, i) => 15 * (i + 1))
                        .attr('x', r ? 30 : 10)
                        .attr('class', self.getResultClassFromThing)
                        .classed('fill', true)
                        .transition().delay(100)
                        // Text format
                        .text((step, i) => `${i + 1}. ${step.name} ${duration(step)}`);
            };
        }

        mouseMove(build) {
            const e = self.d3.select(this);

            // Move the tooltip to the mouse position
            const mouse = self.d3.mouse(this);
            return e.select('.svg-tooltip')
                .attr('transform', `translate(${mouse[0]}, ${mouse[1]})`);
        }

        mouseOut(build) {
            const e = self.d3.select(this);
            self.removeTicks();
            self.drawYAxis();

            // Remove tooltip
            return e.selectAll('.svg-tooltip').remove();
        }

        click(build) {
            // Open modal on click
            let modal;
            return modal = self.$uibModal.open({
                template: require('./modal/modal.tpl.jade'),
                controller: 'waterfallModalController as modal',
                windowClass: 'modal-small',
                resolve: {
                    selectedBuild() { return build; }
                }
            });
        }

        toggleTag(tag) {
            if (!this.$scope.tags_filter.includes(tag)) {
                this.$scope.tags_filter.push(tag);
            } else {
                this.$scope.tags_filter = _.remove(this.$scope.tags_filter, function(currentTag) {
                    return currentTag != tag;
                });
            }
            this.$location.search("tags", this.$scope.tags_filter);
        }

        isTagFiltered(tag) {
            if (this.$scope.tags_filter.includes(tag)) {
                return true;
            } else {
                return false;
            }
        }

        clearTags() {
            this.$scope.tags_filter = this.tags_filter = [];
            this.$location.search("tags", this.$scope.tags_filter);
        }

        makeTagBuilders(currentTags, builders) {
            let tag_builders = [];
            let anyTagSelected = false;
            if (typeof currentTags != 'string') {
                anyTagSelected = true;
                for (const builder of builders) {
                    let v = currentTags.every(currentTag =>
                        builder.tags.includes(currentTag));
                    if (v) {
                        tag_builders.push(builder);
                    }
                }
            } else if (typeof currentTags == 'string') {
                anyTagSelected = true;
                for (const builder of builders) {
                    if (builder.tags.includes(currentTags)) {
                        tag_builders.push(builder);
                    }
                }
            }
            return [anyTagSelected, tag_builders];
        }

        renderNewData(currentTags) {
            currentTags = this.$location.search()['tags'];
            if (currentTags != null) {
                if (typeof currentTags == 'string') {
                    this.$scope.tags_filter = this.tags_filter = [currentTags];
                } else {
                    this.$scope.tags_filter = this.tags_filter = currentTags;
                }
            }
            this.groups = this.dataProcessorService.getGroups(this.all_builders, this.builds, this.c.threshold);
            if (this.s.show_builders_without_builds.value) {
                this.$scope.builders = this.all_builders;
            } else {
                this.$scope.builders = (this.builders = this.dataProcessorService.filterBuilders(this.all_builders));
            }
            if (!this.s.show_old_builders.value) {
                const ret = [];
                for (let builder of this.$scope.builders) {
                    if (this.hasActiveMaster(builder)) {
                        ret.push(builder);
                    }
                }
                this.$scope.builders = this.builders = ret;
            }
            var all_tags = [];
            for (let builder of this.builders) {
                for (let tag of builder.tags) {
                    if (!all_tags.includes(tag)) {
                        all_tags.push(tag);
                    }
                }
            }
            all_tags.sort();
            this.$scope.all_tags = this.all_tags = all_tags;
            this.dataProcessorService.addStatus(this.builders);

            let anyTagSelected, tag_builders;

            if (currentTags != null) {
                [anyTagSelected, tag_builders] = this.makeTagBuilders(currentTags, this.$scope.builders);
            }

            if (anyTagSelected) {
                this.$scope.builders = this.builders = tag_builders;
            }
            this.render();
            return this.loadingMore = false;
        }

        /*
         * Render the waterfall view
         */
        render() {

            const containerParent = this.container.node().parentNode;
            const y = this.scale.getY(this.groups, this.c.gap, this.getInnerHeight());
            const time = y.invert(containerParent.scrollTop);

            // Set the content width
            this.setWidth();

            // Set the height of the container
            this.setHeight();

            // Draw the waterfall
            this.drawBuilds();
            this.drawXAxis();
            this.drawYAxis();
        }
    };
    Cls.initClass();
    return Cls;
})();

angular.module('waterfall_view', [
    'ui.router',
    'ngAnimate',
    'guanlecoja.ui',
    'bbData',
])
.controller('waterfallController', ['$rootElement', '$scope', '$q', '$timeout', '$window', '$log',
                                    '$uibModal', 'dataService', 'd3Service', 'dataProcessorService',
                                    'scaleService', 'bbSettingsService',
                                    'glTopbarContextualActionsService', '$location', '$rootScope',
                                    WaterfallController])
.config(['$locationProvider', function($locationProvider) {
    $locationProvider.hashPrefix('');
}]);

require('./dataProcessor/dataProcessor.service.js');
require('./main.module.js');
require('./modal/modal.controller.js');
require('./scale/scale.service.js');
require('./waterfall.config.js');
require('./waterfall.route.js');
