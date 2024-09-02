/*
  This file is part of Buildbot.  Buildbot is free software: you can
  redistribute it and/or modify it under the terms of the GNU General Public
  License as published by the Free Software Foundation, version 2.

  This program is distributed in the hope that it will be useful, but WITHOUT
  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
  FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
  details.

  You should have received a copy of the GNU General Public License along with
  this program; if not, write to the Free Software Foundation, Inc., 51
  Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

  Copyright Buildbot Team Members
*/

import * as d3 from "d3";
import {Build, Builder, Step, results2class} from "buildbot-data-js";
import {BuildGroup, WaterfallYScale} from "./Utils";

export type MarginSettings = {
  top: number;
  right: number;
  bottom: number;
  left: number;
};

export type LayoutSettings = {
  margin: MarginSettings;
  gap: number;
};

function pushTickValue(ticks: number[], y: WaterfallYScale, value: number) {
  const tick = y.getCoord(value);
  if (tick !== undefined) {
    ticks.push(tick);
  }
}

function link(formatter) {
  function linkImpl(this: d3.BaseType, d: unknown) {
    const el = this as Element;
    if (el.parentNode === null) {
      return;
    }
    const p = d3.select(el.parentElement);
    const a = p.append('a')
      .attr('xlink:href', formatter(d));
    a.node()?.appendChild(el);
  };
  return linkImpl;
};


export class Visualizer {
  minColumnWidth: number;
  showBuildNumberBackground: boolean;
  layoutSettings: LayoutSettings;

  waterfall!: d3.Selection<HTMLDivElement, unknown, null, unknown>;
  container!: d3.Selection<HTMLDivElement, unknown, null, unknown>;
  header!: d3.Selection<HTMLDivElement, unknown, null, unknown>;
  chart!: d3.Selection<SVGGElement, unknown, null, unknown>;
  headerSvg!: d3.Selection<SVGGElement, unknown, null, unknown>;
  containerWidth!: number;
  contentWidth!: number;
  containerHeight!: number;
  contentHeight!: number;

  setHoveredBuildId: (buildid: number|null) => void;
  hoveredBuild: Build|null = null;
  hoveredBuildTooltip: d3.Selection<SVGGElement, unknown, null, unknown>|null = null;
  hoveredBuildTooltipOnRight: boolean = false;
  extraTicks: number[] = [];

  hasViewConfig = false;
  rootEl!: HTMLDivElement;
  headerEl!: HTMLDivElement;
  headerContentEl!: HTMLDivElement;
  contentEl!: HTMLDivElement;
  innerContentEl!: HTMLDivElement;
  svgContainerEl!: HTMLDivElement;
  // Window width is only used to detect layout changes, the actual element width is taken from
  // rootEl.
  windowWidth: number = 0;
  scalingFactor: number = 1;

  builders: Builder[] = [];
  buildGroups: BuildGroup[] = [];
  builderToBuilds: Map<number, Build[]> = new Map<number, Build[]>();

  constructor(setHoveredBuildId: (buildid: number|null) => void,
              minColumnWidth: number, showBuildNumberBackground: boolean,
              layoutSettings: LayoutSettings) {
    this.setHoveredBuildId = setHoveredBuildId;
    this.minColumnWidth = minColumnWidth;
    this.showBuildNumberBackground = showBuildNumberBackground;
    this.layoutSettings = layoutSettings;

    if (this.minColumnWidth <= 0) {
      console.error(`Bad column width configuration\n\t min: ${this.minColumnWidth}`);
      this.minColumnWidth = 10;
    }
  }

  onViewConfigMaybeUpdate(rootEl: HTMLDivElement|null, headerEl: HTMLDivElement|null,
                          headerContentEl: HTMLDivElement|null, contentEl: HTMLDivElement|null,
                          innerContentEl: HTMLDivElement|null, svgContainerEl: HTMLDivElement|null,
                          windowWidth: number, scalingFactor: number) {
    if (rootEl === null || headerEl === null || headerContentEl === null || contentEl === null ||
      innerContentEl === null || svgContainerEl === null) {
      return;
    }

    if (this.rootEl === rootEl &&
      this.headerEl === headerEl &&
      this.headerContentEl === headerContentEl &&
      this.contentEl === contentEl &&
      this.innerContentEl === innerContentEl &&
      this.svgContainerEl === svgContainerEl &&
      this.windowWidth === windowWidth &&
      this.scalingFactor === scalingFactor) {
      return;
    }
    this.hasViewConfig = true;
    this.rootEl = rootEl;
    this.headerEl = headerEl;
    this.headerContentEl = headerContentEl;
    this.contentEl = contentEl;
    this.innerContentEl = innerContentEl;
    this.svgContainerEl = svgContainerEl;
    this.windowWidth = windowWidth;
    this.scalingFactor = scalingFactor;

    this.waterfall = d3.select(this.rootEl);
    this.container = d3.select(this.svgContainerEl);
    this.header = d3.select(this.headerContentEl);

    this.createElements();

    this.render();
  }

  onData(builders: Builder[], buildGroups: BuildGroup[], builderToBuilds: Map<number, Build[]>) {
    this.builders = builders;
    this.buildGroups = buildGroups;
    this.builderToBuilds = builderToBuilds;
    this.render();
  }

  render() {
    if (!this.hasViewConfig) {
      return;
    }

    this.setContentWidth();
    this.setContentHeight();

    this.drawBuilds();

    this.drawXAxis();
    this.drawYAxis();
  }

  getClassForBuilderResults(builder: Builder) {
    const builds = this.builderToBuilds.get(builder.builderid);
    return results2class(builds === undefined ? null : builds[0], null);
  }

  getHeaderHeight() {
    let maxNameLength = 0;
    for (const builder of this.builders) {
      maxNameLength = Math.max(builder.name.length, maxNameLength);
    }
    return Math.max(100, maxNameLength * 3);
  }

  createElements() {
    const ls = this.layoutSettings;

    // Remove any unwanted elements first
    this.container.selectAll('*').remove();
    this.header.selectAll('*').remove();


    this.chart = this.container.append('svg')
      .append('g')
      .attr('transform', `translate(${ls.margin.left}, ${ls.margin.top})`)
      .attr('class', 'chart');

    const height = this.getHeaderHeight();
    this.waterfall.select(".header").style("height", height);

    this.headerSvg = this.header.append('svg')
      .append('g')
      .attr('transform', `translate(${ls.margin.left}, ${height})`)
      .attr('class', 'header');
  }

  setContentWidth() {
    const totalMargins = this.layoutSettings.margin.right + this.layoutSettings.margin.left

    const availableWidth = this.rootEl.offsetWidth - totalMargins;
    const minRequiredWidth = this.builders.length * this.minColumnWidth;

    const expand = availableWidth >= minRequiredWidth;

    const width = expand ? '100%' : `${minRequiredWidth + totalMargins}px`;
    this.waterfall.select('.inner-content').style('width', width);
    this.waterfall.select('.header-content').style('width', width);

    this.contentWidth = expand ? availableWidth : minRequiredWidth;
    this.containerWidth = this.contentWidth + totalMargins;
  }

  setContentHeight() {
    const ls = this.layoutSettings;

    let h = -ls.gap;
    for (const group of this.buildGroups) {
      h += ((group.maxTime - group.minTime) + ls.gap);
    }

    const totalMargins = ls.margin.top + ls.margin.bottom;

    this.contentHeight = h * this.scalingFactor;
    this.containerHeight = this.contentHeight + totalMargins;

    this.container.style('height', `${this.containerHeight}px`);

    const headerHeight = this.getHeaderHeight();
    this.waterfall.select("div.header").style("height", headerHeight + "px");
    this.headerSvg.attr('transform', `translate(${ls.margin.left}, ${headerHeight})`);
  }

  getScaleX() {
    return d3.scaleBand()
      .domain(this.builders.map(builder => builder.builderid.toString()))
      .rangeRound([0, this.contentWidth])
      .padding(0.05);
  }

  getBuilderNameTickFormat() {
    return d3.scaleOrdinal<string>()
      .domain(this.builders.map(builder => builder.builderid.toString()))
      .range(this.builders.map(builder => builder.name));
  }

// Returns y scale
  getScaleY() {
    return new WaterfallYScale(this.buildGroups, this.layoutSettings.gap, this.contentHeight);
  }

  getTickValues(y: WaterfallYScale) {
    const ticks = [...this.extraTicks];
    for (const group of this.buildGroups) {
      pushTickValue(ticks, y, group.minTime);
      pushTickValue(ticks, y, group.maxTime);
    }
    return ticks;
  }

  setExtraTicksForBuild(build: Build) {
    const y = this.getScaleY();
    const ticks: number[] = [];
    if (build.complete_at !== null) {
      pushTickValue(ticks, y, build.complete_at);
    }
    pushTickValue(ticks, y, build.started_at);
    this.extraTicks = ticks;
  }

  drawXAxis() {
    const x = this.getScaleX();

    // Remove old axis
    this.headerSvg.select('.axis.x').remove();

    // Select axis
    const axis = this.headerSvg.append('g')
      .attr('class', 'axis x');

    // Remove previous elements
    axis.selectAll('*').remove();

    // Top axis shows builder names
    const xAxis = d3.axisTop(x)
      .tickFormat(this.getBuilderNameTickFormat());

    const xAxisSelect = axis.call(xAxis);

    // Rotate text
    xAxisSelect.selectAll('text')
      .style('text-anchor', 'start')
      .attr('transform', 'translate(0, -16) rotate(-25)')
      .attr('dy', '0.75em')
      .each(link(builderid => `#/builders/${builderid}`));

    // Rotate tick lines
    xAxisSelect.selectAll('line')
      .data(this.builders)
      .attr('transform', 'rotate(90)')
      .attr('x1', 0)
      .attr('x2', 0)
      .attr('y1', x.bandwidth() / 2)
      .attr('y2', -x.bandwidth() / 2)
      .attr('class', b => this.getClassForBuilderResults(b))
      .classed('stroke', true);
  }

  drawYAxis() {
    const i = d3.scaleLinear();
    const y = this.getScaleY();

    // Remove old axis
    this.chart.select('.axis.y').remove();

    const axis = this.chart.append('g')
      .attr('class', 'axis y');

    // White background
    axis.append('rect')
      .attr('x', -this.layoutSettings.margin.left)
      .attr('y', -this.layoutSettings.margin.top)
      .attr('width', this.layoutSettings.margin.left)
      .attr('height', this.containerHeight)
      .style('fill', '#fff');

    const ticks = this.getTickValues(y);

    // Y axis time format (new line: ^)
    const timeFormat = '%x^%H:%M';

    const tickFormat = (coordinate: number) => {
      const timestamp = y.invert(coordinate);
      if (timestamp === undefined) {
        return '';
      }
      const date = new Date(timestamp * 1000);
      const format = d3.timeFormat(timeFormat);
      return format(date);
    };

    const yAxis = d3.axisLeft<number>(i)
      .tickValues(ticks)
      .tickFormat(tickFormat);

    const yAxisSelect = axis.call(yAxis);

    // Break text on ^ character
    function lineBreak(this: d3.BaseType) {
      const e = d3.select(this);
      const words = e.text().split('^');
      e.text('');

      for (let i = 0; i < words.length; i++) {
        const word = words[i];
        const text = e.append('tspan').text(word);
        if (i !== 0) {
          const x = e.attr('x');
          text.attr('x', x).attr('dy', i * 10);
        }
      }
    };
    yAxisSelect.selectAll('text').each(lineBreak);

    const dasharray = (tick: any) => this.extraTicks.includes(tick) ? '2, 5' : '2, 1';

    yAxisSelect.selectAll('.tick')
      .append('line')
      .attr('x2', this.contentWidth)
      .attr('stroke-dasharray', dasharray);

    // Stay on left on horizontal scrolling
    axis.attr('transform', `translate(${this.rootEl.scrollLeft}, 0)`);
    this.waterfall.on('scroll',
      () => { yAxisSelect.attr('transform', `translate(${this.rootEl.scrollLeft}, 0)`); });
  }

  getPoinstForTooltip(height: number, tooltipOnRight: boolean) {
    if (tooltipOnRight) {
      return `20,0 0,${height / 2} 20,${height} 170,${height} 170,0`;
    } else {
      return `150,0 170,${height / 2} 150,${height} 0,${height} 0,0`;
    }
  }

  onHoveredBuildSteps(steps: Step[]) {
    if (this.hoveredBuildTooltip === null) {
      return;
    }

    const height = (steps.length * 15) + 7;
    this.hoveredBuildTooltip.transition().duration(100)
      .attr('transform', `translate(${this.hoveredBuildTooltipOnRight ? 5 : -175}, ${- height / 2})`)
      .select('polygon')
      .attr('points', this.getPoinstForTooltip(height, this.hoveredBuildTooltipOnRight));

    const duration = function(step: Step) {
      const d = ((step.complete_at ?? 0) - (step.started_at ?? 0)) * 1000;
      if (d > 0) {
        return `(${d / 1000}s)`;
      } else {
        return '';
      }
    };

    this.hoveredBuildTooltip.selectAll('.buildstep')
      .data(steps)
      .enter().append('g')
      .attr('class', 'buildstep')
      // Add text
      .append('text')
      .attr('y', (step, i) => 15 * (i + 1))
      .attr('x', this.hoveredBuildTooltipOnRight ? 30 : 10)
      .attr('class', b => results2class(b, null))
      .classed('fill', true)
      .transition().delay(100)
      // Text format
      .text((step, i) => `${i + 1}. ${step.name} ${duration(step)}`);
  }

  mouseOver(node: d3.ContainerElement, build: Build) {
    if (node.parentElement === null) {
      return;
    }

    const e = d3.select(node);
    const mouse = d3.mouse(node);
    this.setExtraTicksForBuild(build);
    this.drawYAxis();

    // Move build and builder to front
    const p = d3.select(node.parentElement);
    node.parentElement.appendChild(node);
    p.each(function(this: Element) { return this.parentElement?.appendChild(this); });

    // Show tooltip on the left or on the right
    const tooltipOnRight = build.builderid < (this.builders.length / 2);

    // Create tooltip
    let height = 40;
    const tooltip = e.append('g')
      .attr('class', 'svg-tooltip')
      .attr('transform', `translate(${mouse[0]}, ${mouse[1]})`)
      .append('g')
      .attr('class', 'tooltip-content')
      .attr('transform', `translate(${tooltipOnRight ? 5 : -175}, ${- height / 2})`);

    tooltip.append('polygon')
      .attr('points', this.getPoinstForTooltip(height, tooltipOnRight));

    this.hoveredBuild = build;
    this.hoveredBuildTooltip = tooltip;
    this.hoveredBuildTooltipOnRight = tooltipOnRight;
    this.setHoveredBuildId(build.buildid);
  }

  mouseMove(node: d3.ContainerElement) {
    const e = d3.select(node);

    // Move the tooltip to the mouse position
    const mouse = d3.mouse(node);
    e.select('.svg-tooltip')
      .attr('transform', `translate(${mouse[0]}, ${mouse[1]})`);
  }

  mouseOut(node: d3.ContainerElement) {
    const e = d3.select(node);
    this.extraTicks = [];
    this.drawYAxis();

    this.hoveredBuild = null;
    this.hoveredBuildTooltip = null;
    this.setHoveredBuildId(null);

    // Remove tooltip
    e.selectAll('.svg-tooltip').remove();
  }

  drawBuilds() {
    const x = this.getScaleX();
    const y = this.getScaleY();

    this.chart.selectAll('.builder').remove();

    // Create builder columns
    const builderEls = this.chart.selectAll('.builder')
      .data(this.builders).enter()
      .append('g')
      .attr('class', 'builder')
      .attr('transform', (builder: Builder) => `translate(${x(builder.builderid.toString())}, 0)`);

    // Create build group for each build
    const data = (builder: Builder) => this.builderToBuilds.get(builder.builderid) ?? [];
    const key = (build: Build) => build.buildid.toString();

    const builds = builderEls.selectAll<d3.BaseType, Build>('.build')
      .data(data, key).enter()
      .append('g')
      .attr('class', 'build')
      .attr('transform', (build: Build) => `translate(0, ${y.getCoord(build.complete_at ?? 0)})`);

    // Draw rectangle for each build
    const height = (build: Build) => {
      return Math.max(10,
        Math.abs((y.getCoord(build.started_at) ?? 0) -
          (y.getCoord(build.complete_at ?? 0) ?? 0)));
    }

    const buildlink = link(b => `#/builders/${b.builderid}/builds/${b.number}`);

    builds.append('rect')
      .attr('class', b => results2class(b, null))
      .attr('width', x.bandwidth())
      .attr('height', height)
      .classed('fill', true)
      .each(buildlink);

    // Optional: grey rectangle below buildids
    if (this.showBuildNumberBackground) {
      builds.append('rect')
        .attr('y', -15)
        .attr('width', x.bandwidth())
        .attr('height', 15)
        .style('fill', '#ccc');
    }

    // Draw text over builds
    builds.append('text')
      .attr('class', 'id')
      .attr('x', x.bandwidth() / 2)
      .attr('y', -3)
      .text(build => build.number)
      .each(buildlink);

    const self = this;

    // Add event listeners
    builds
      .on('mouseover', function(this: d3.ContainerElement, build: Build) {
        self.mouseOver(this, build);
      })
      .on('mousemove', function(this: d3.ContainerElement) { self.mouseMove(this); })
      .on('mouseout', function(this: d3.ContainerElement) { self.mouseOut(this); })
  }

}
