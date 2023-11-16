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

import './WaterfallView.scss';
import {autorun} from "mobx";
import {observer} from "mobx-react";
import {useEffect, useRef, useState} from "react";
import {useHotkeys} from "react-hotkeys-hook";
import {
  FaChartBar,
  FaSearchMinus,
  FaSearchPlus
} from "react-icons/fa";
import {buildbotGetSettings, buildbotSetupPlugin} from "buildbot-plugin-support";
import {
  useDataAccessor,
  useDataApiDynamicQuery,
  useDataApiDynamicQueryResolved,
  useDataApiQuery,
  Build,
  Builder,
  DataCollection,
  Master,
  Step, stepDescriptor
} from "buildbot-data-js";
import {
  LoadingIndicator,
  TagFilterManager,
  TagFilterManagerTagMode,
  hasActiveMaster,
  useTagFilterManager,
  useTopbarActions,
  useWindowSize
} from "buildbot-ui";
import {groupBuildsByTime, groupBuildsPerBuilder} from "./Utils";
import {LayoutSettings, Visualizer} from "./Visualizer";

const isBuilderFiltered = (builder: Builder, filterManager: TagFilterManager,
                           masters: DataCollection<Master>,
                           builderToBuilds: Map<number, Build[]>,
                           showBuildersWithoutBuilds: boolean,
                           showOldBuilders: boolean) => {
  if (!showOldBuilders && !hasActiveMaster(builder, masters)) {
    return false;
  }

  if (!showBuildersWithoutBuilds && !builderToBuilds.has(builder.builderid)) {
    return false;
  }

  return filterManager.shouldShowByTags(builder.tags);
}

const isBuilderFilteredHasMaster = (builder: Builder, masters: DataCollection<Master>,
                                    showOldBuilders: boolean) => {
  if (!showOldBuilders && !hasActiveMaster(builder, masters)) {
    return false;
  }
  return true;
}

const getAllTags = (builders: Builder[]) => {
  const tags = new Set<string>();
  for (const builder of builders) {
    for (const tag of builder.tags) {
      tags.add(tag);
    }
  }
  const tagsArray = [...tags.keys()];
  tagsArray.sort((a, b) => a.localeCompare(b));
  return tagsArray;
}

export const WaterfallView = observer(() => {
  const accessor = useDataAccessor([]);
  const windowSize = useWindowSize();

  const filterManager = useTagFilterManager("tags", TagFilterManagerTagMode.ToggleOnOff);

  const rootRef = useRef<HTMLDivElement|null>(null);
  const headerRef = useRef<HTMLDivElement|null>(null);
  const headerContentRef = useRef<HTMLDivElement|null>(null);
  const contentRef = useRef<HTMLDivElement|null>(null);
  const innerContentRef = useRef<HTMLDivElement|null>(null)
  const svgContainerRef = useRef<HTMLDivElement|null>(null);

  const settings = buildbotGetSettings();
  const [scalingFactor, setScalingFactor] =
    useState(() => settings.getIntegerSetting("Waterfall.scaling_waterfall"));
  const lazyLoadingLimit = settings.getIntegerSetting("Waterfall.lazy_limit_waterfall");
  const showBuildersWithoutBuilds =
    settings.getBooleanSetting("Waterfall.show_builders_without_builds");
  const [showOldBuilders, setShowOldBuilders] =
    useState(() => settings.getBooleanSetting("Waterfall.show_old_builders"));

  const [currBuildLimit, setCurrBuildLimit] = useState(lazyLoadingLimit);
  const [hoveredBuildId, setHoveredBuildId] = useState<number|null>(null);

  const buildersQuery = useDataApiQuery(() => Builder.getAll(accessor, {query: {order: 'name'}}));
  const mastersQuery = useDataApiQuery(() => Master.getAll(accessor));
  const buildsQuery = useDataApiDynamicQueryResolved([currBuildLimit], () =>
    Build.getAll(accessor, {query: {limit: currBuildLimit, order: '-started_at'}}));
  const buildStepsQuery = useDataApiDynamicQuery([hoveredBuildId],
    () => {
      if (hoveredBuildId === null) {
        return new DataCollection<Step>();
      }
      return accessor.get<Step>(`builds/${hoveredBuildId}/steps`, {}, stepDescriptor);
    });

  const queriesResolved = buildersQuery.resolved &&
    mastersQuery.resolved &&
    buildsQuery.resolved;

  const layoutSettings: LayoutSettings = {
    // Margins around the chart
    margin: {
      top: 15,
      right: 20,
      bottom: 20,
      left: 70
    },

    // Gap between groups (px)
    gap: 30,
  };

  const [visualizer, _] = useState(() => new Visualizer(
    setHoveredBuildId,
    settings.getIntegerSetting("Waterfall.min_column_width_waterfall"),
    settings.getBooleanSetting("Waterfall.number_background_waterfall"),
    layoutSettings));

  const changeScalingFactor = (multiplier: number) => {
    const newScaling = scalingFactor * multiplier;
    setScalingFactor(newScaling);
    settings.setSetting("Waterfall.scaling_waterfall", newScaling);
    settings.save();
  };

  const increaseScalingFactor = () => changeScalingFactor(1.5);
  const decreaseScalingFactor = () => changeScalingFactor(1 / 1.5);

  useTopbarActions([
    {
      caption: "",
      icon: <FaSearchPlus/>,
      action: increaseScalingFactor,
    }, {
      caption: "",
      icon: <FaSearchMinus/>,
      action: decreaseScalingFactor,
    }
  ]);

  useHotkeys('+', () => increaseScalingFactor());
  useHotkeys('-', () => decreaseScalingFactor());

  useEffect(() => {
    return autorun(() => {
      const builderToBuilds = groupBuildsPerBuilder(buildsQuery.array);
      const buildersToShow = buildersQuery.array.filter(b =>
        isBuilderFiltered(b, filterManager, mastersQuery, builderToBuilds, showBuildersWithoutBuilds,
          showOldBuilders));
      const builderIds = new Set<number>(buildersToShow.keys());
      const buildGroups = groupBuildsByTime(builderIds, buildsQuery.array,
        settings.getIntegerSetting("Waterfall.idle_threshold_waterfall"), Date.now() / 1000);

      visualizer.onData(buildersToShow, buildGroups, builderToBuilds);
    })
    // FIXME: buildsQuery could be improved
  }, [showOldBuilders, buildsQuery.array.length, filterManager.tags]);

  useEffect(() => {
    visualizer.onViewConfigMaybeUpdate(rootRef.current, headerRef.current, headerContentRef.current,
      contentRef.current, innerContentRef.current, svgContainerRef.current, windowSize.width,
      scalingFactor);
  });

  useEffect(() => {
    return autorun(() => {
      visualizer.onHoveredBuildSteps(buildStepsQuery.array);
    })
  }, [buildStepsQuery]);

  const onScroll = () => {
    if (buildsQuery.array.length < currBuildLimit) {
      // Data is still being loaded
      return;
    }

    if ((visualizer.containerHeight - innerContentRef.current!.scrollTop) < 1000) {
      setCurrBuildLimit(limit => limit + lazyLoadingLimit);
    }
  };

  if (!queriesResolved) {
    return (
      <div ref={rootRef} className="container bb-waterfall-view">
        <LoadingIndicator/>
      </div>
    );
  }

  const buildersForTags = buildersQuery.array.filter(b =>
    isBuilderFilteredHasMaster(b, mastersQuery, showOldBuilders));

  return (
    <div ref={rootRef} className="container bb-waterfall-view">
      <div><p>Tags: {filterManager.getElementsForTags(getAllTags(buildersForTags))}</p></div>
      <div ref={headerRef} className="header">
        <div ref={headerContentRef} className="header-content"></div>
      </div>
      <div ref={contentRef} className="content">
        <div ref={innerContentRef} onScroll={onScroll} className="inner-content">
          <div ref={svgContainerRef} className="svg-container"></div>
        </div>
      </div>
    </div>
  );
});

buildbotSetupPlugin(reg => {
  reg.registerMenuGroup({
    name: 'waterfall',
    caption: 'Waterfall View',
    icon: <FaChartBar/>,
    order: 5,
    route: '/waterfall',
    parentName: null,
  });

  reg.registerRoute({
    route: "/waterfall",
    group: "waterfall",
    element: () => <WaterfallView/>,
  });

  reg.registerSettingGroup({
    name: 'Waterfall',
    caption: 'Waterfall related settings',
    items: [{
        type: 'integer',
        name: 'scaling_waterfall',
        caption: 'Scaling factor',
        defaultValue: 1
      }, {
        type: 'integer',
        name: 'min_column_width_waterfall',
        caption: 'Minimum column width (px)',
        defaultValue: 40
      }, {
        type: 'integer',
        name: 'lazy_limit_waterfall',
        caption: 'Lazy loading limit',
        defaultValue: 40
      }, {
        type: 'integer',
        name: 'idle_threshold_waterfall',
        caption: 'Idle time threshold in unix time stamp (eg. 300 = 5 min)',
        defaultValue: 300
      }, {
        type: 'boolean',
        name: 'number_background_waterfall',
        caption: 'Build number background',
        defaultValue: false
      }, {
        type: 'boolean',
        name: 'show_builders_without_builds',
        caption: 'Show builders without builds',
        defaultValue: false
      }, {
        type: 'boolean',
        name: 'show_old_builders',
        caption: 'Show old builders',
        defaultValue: false
      }
    ]
  });
});

export default WaterfallView;
