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

import {useContext} from "react";
import {ConfigContext} from "../../contexts/Config";
import {observer} from "mobx-react";
import {Step} from "../../data/classes/Step";
import {useDataAccessor, useDataApiQuery} from "../../data/ReactUtils";
import {Builder} from "../../data/classes/Builder";
import {Build} from "../../data/classes/Build";
import {results2class, results2text} from "../../util/Results";
import {durationFormat, useCurrentTime} from "../../util/Moment";
import {getPropertyValueOrDefault} from "../../util/Properties";
import {analyzeStepUrls, useStepUrlAnalyzer} from "../../util/StepUrls";

const isStepDisplayed = (step: Step) => {
  return !step.hidden;
}

const limitStringLength = (s: string, limit: number) => {
  let res = s.slice(0, limit);
  if (s.length > limit) {
    res += ' ...';
  }
  return res;
}

type BuildSummaryTooltipProps = {
  build: Build;
}

const BuildSummaryTooltip = observer(({build}: BuildSummaryTooltipProps) => {
  const accessor = useDataAccessor();
  const config = useContext(ConfigContext);

  const propertiesQuery = useDataApiQuery(() => build.getProperties());
  const stepsQuery = useDataApiQuery(() => build.getSteps());
  const builderQuery = useDataApiQuery(() => Builder.getAll(accessor, {id: build.builderid.toString()}));

  const builder = builderQuery.getNthOrNull(0);
  const stepsToDisplay = stepsQuery.array.filter(isStepDisplayed);

  const buildResultClass = build !== null ? " " + results2class(build, null) : "";

  const reason = getPropertyValueOrDefault(propertiesQuery.properties, "reason", null);

  const baseUrls = config.buildbotURLs || [config.buildbotURL];
  const stepUrlAnalyzer = useStepUrlAnalyzer(baseUrls);

  const now = useCurrentTime();

  const headerElements: JSX.Element[] = [];

  if (build !== null) {
    headerElements.push((
      <div className="flex-row">
        <div className="flex-grow-1">
          <span>{builder !== null ? limitStringLength(builder.name, 80) : ''}</span>
          <span className={"badge-status" + buildResultClass}>{build.number}</span>
          { reason !== null
            ? <span>&nbsp; | {reason}</span>
            : <></>
          }
        </div>
      </div>
    ));

    headerElements.push((
      <div className="flex-row">
        <div className="flex-grow-1">
          {
            build.complete
              ? <span>{durationFormat(build.complete_at! - build.started_at)}</span>
              : <span>{durationFormat(now - build.started_at)}</span>
          }
          { limitStringLength(build.state_string, 80) }
          &nbsp;
          <div className={"label bb-build-result" + buildResultClass}>{results2text(build)}</div>
        </div>
      </div>
    ));
  } else {
    headerElements.push((
      <div className="flex-row">loading build details...</div>
    ));
  }

  const stepElements = stepsToDisplay.map((step, index) => {
    if (index >= 3 && index < stepsToDisplay.length - 3) {
      if (index === 3) {
        return (
          <li key={index} className="list-group-item">
            <div className="text-left">
              <span className="fa-lg">⋮</span>
            </div>
          </li>
        )
      } else {
        return <></>;
      }
    }

    let stepInfoWhenStarted: JSX.Element | null = null;
    if (step.started_at !== null) {
      stepInfoWhenStarted = (
        <span className="pull-right">
            {
              step.complete
                ? <span>{durationFormat(step.complete_at! - step.started_at)}</span>
                : <span>{durationFormat(now - step.started_at)}</span>
            }
          {limitStringLength(step.state_string, 40)}
        </span>
      );
    }

    const stepInfo = analyzeStepUrls(stepUrlAnalyzer, step.urls);

    let stepBuildInfoElement: JSX.Element | null = null;
    if (stepInfo.buildrequests.length > 0) {
      stepBuildInfoElement = (
        <span>
          {stepInfo.builds.length} builds,
          {stepInfo.buildrequests.length - stepInfo.builds.length} pending builds
        </span>
      );
    }

    return (
      <li key={index} className="list-group-item">
        <div className="clearfix">
          <span className="pull-left">
            <span className={"badge-status " + results2class(step, 'pulse')}>{step.number}</span>
            &nbsp;
          </span>
          <span className="pull-left">{limitStringLength(step.name, 40)}
            {stepBuildInfoElement}
          </span>
          <span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>
          {stepInfoWhenStarted}
        </div>
      </li>
    )
  });

  return (
    <div style={{marginBottom: "0px"}}
         className={"panel panel-default" + buildResultClass}>
      <div className="panel-heading">
        {headerElements}
      </div>
      <ul className="list-group">
        {stepElements}
      </ul>
    </div>
  );
});

export default BuildSummaryTooltip;
