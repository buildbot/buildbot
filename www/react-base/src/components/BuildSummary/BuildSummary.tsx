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

import './BuildSummary.scss';
import {observer} from "mobx-react";
import {results2class, results2text, SUCCESS} from "../../util/Results";
import {useContext, useState} from "react";
import {ConfigContext} from "../../contexts/Config";
import {useDataAccessor, useDataApiDynamicQuery, useDataApiQuery} from "../../data/ReactUtils";
import {analyzeStepUrls, useStepUrlAnalyzer} from "../../util/StepUrls";
import {durationFormat, useCurrentTime} from "../../util/Moment";
import {Log} from "../../data/classes/Log";
import {globalSettings} from "../../plugins/GlobalSettings";
import {Step} from "../../data/classes/Step";
import {Build} from "../../data/classes/Build";
import {Builder} from "../../data/classes/Builder";
import {getPropertyValueOrDefault} from "../../util/Properties";
import {Link} from "react-router-dom";
import DataCollection from "../../data/DataCollection";
import LogPreview from "../LogPreview/LogPreview";
import {useStateWithParentTrackingWithDefaultIfNotSet} from "../../util/React";
import ArrowExpander from "../ArrowExpander/ArrowExpander";
import BuildRequestSummary from "../BuildRequestSummary/BuildRequestSummary";
import BadgeRound from "../BadgeRound/BadgeRound";
import BadgeStatus from "../BadgeStatus/BadgeStatus";
import {Card} from "react-bootstrap";

enum DetailLevel {
  None = 0,
  OnlyNotSuccess = 1,
  Everything = 2,
  Count = 3
}

const detailLevelToString = (level: DetailLevel) => {
  switch (level) {
    case DetailLevel.None:
      return "None";
    case DetailLevel.OnlyNotSuccess:
      return "Problems";
    case DetailLevel.Everything:
    default:
      return "All";
  }
}

const isStepDisplayed = (step: Step, details: DetailLevel) => {
  if (details === DetailLevel.Everything) {
    return !step.hidden;
  } else if (details === DetailLevel.OnlyNotSuccess) {
    return (step.results == null) || (step.results !== SUCCESS);
  } else if (details === DetailLevel.None) {
    return false;
  }
}

const shouldExpandLog = (log: Log, logsToExpand: string) => {
  if (log.num_lines === 0) {
    return false;
  }
  return logsToExpand.toLowerCase().split(";").includes(log.name.toLowerCase());
};

const isSummaryLog = (log: Log)  => log.name.toLowerCase() === "summary";

// Returns the logs, sorted with the "Summary" log first, if it exists in the step's list of logs
const getStepLogsInDisplayOrder = (logs: DataCollection<Log>) => {
  const summaryLogs = logs.array.filter(log => isSummaryLog(log));
  return summaryLogs.concat(logs.array.filter(log => !isSummaryLog(log)));
};

type BuildSummaryStepLineProps = {
  build: Build;
  step: Step;
  logs: DataCollection<Log>;
  parentFullDisplay: boolean
}

const BuildSummaryStepLine = observer(({build, step, logs, parentFullDisplay}: BuildSummaryStepLineProps) => {
  const config = useContext(ConfigContext);
  const now = useCurrentTime();

  const logsToExpand = globalSettings.getStringSetting("LogPreview.expand_logs");
  const showUrls = globalSettings.getBooleanSetting("Build.show_urls");

  const baseUrls = config.buildbotURLs || [config.buildbotURL];
  const stepUrlAnalyzer = useStepUrlAnalyzer(baseUrls);

  const [fullDisplay, setFullDisplay] = useStateWithParentTrackingWithDefaultIfNotSet(
    parentFullDisplay, () => !step.complete || (step.results !== SUCCESS));

  const renderState = () => {
    if (step.started_at === null) {
      return <></>;
    }

    return (
      <span className="pull-right">
          {
            step.complete
              ? <span>{durationFormat(step.complete_at! - step.started_at)}</span>
              : <span>{durationFormat(now - step.started_at)}</span>
          }
        &nbsp;
        {step.state_string}
        </span>
    );
  }

  const stepInfo = analyzeStepUrls(stepUrlAnalyzer, step.urls);

  const maybeRenderArrowExpander = () => {
    if ( logs.array.length > 0 || stepInfo.buildrequests.length > 0 ||
        (stepInfo.otherUrls.length > 0 && !showUrls)) {
      return <ArrowExpander isExpanded={fullDisplay}/>;
    }
    return null;
  }

  const maybeRenderPendingBuildCount = () => {
    if (stepInfo.buildrequests.length === 0) {
      return null;
    }
    return (
      <span>
        {stepInfo.builds.length} builds,
        {stepInfo.buildrequests.length - stepInfo.builds.length} pending builds
      </span>
    );
  }

  const renderStepUrls = () => {
    const urlElements = stepInfo.otherUrls.map((url, index) => {
      return (
        <li key={index}>
          <a href={url.url} rel="noreferrer" target="_blank">
            {url.name}
          </a>
        </li>
      );
    });

    return <ul>{urlElements}</ul>;
  }

  const renderStepLogs = () => {
    return getStepLogsInDisplayOrder(logs).map(log => {
      const initialFullDisplay = logs.array.length === 1 || shouldExpandLog(log, logsToExpand);
      return (
        <LogPreview key={log.id} builderid={build.builderid} buildnumber={build.number}
                    stepnumber={step.number} log={log} initialFullDisplay={initialFullDisplay}/>
      );
    });
  }

  const renderFullInfo = () => {
    // TODO implement pagination of build requests
    return (
      <div className="anim-stepdetails">
        {!showUrls ? renderStepUrls() : <></>}
        <ul className="list-unstyled group-results">
          {stepInfo.buildrequests.map(brInfo => (
            <li key={brInfo.buildrequestid}>
              <BuildRequestSummary buildrequestid={brInfo.buildrequestid}/>
            </li>
          ))}
        </ul>
        {renderStepLogs()}
      </div>
    );
  }

  return (
    <li key={step.id} className="list-group-item">
      <div onClick={() => setFullDisplay(!fullDisplay)}>
        <BadgeRound className={results2class(step, 'pulse')}>{step.number.toString()}</BadgeRound>
        &nbsp;
        {maybeRenderArrowExpander()}
        &nbsp;
        {step.name}
        {renderState()}
        {maybeRenderPendingBuildCount()}
      </div>
      {showUrls ? renderStepUrls() : <></>}
      {fullDisplay ? renderFullInfo() : <></>}
    </li>
  )
})

type BuildSummaryProps = {
  build: Build;
  parentBuild: Build | null;
  parentRelationship: string | null;
  condensed: boolean;
}

const BuildSummary = observer(({build, parentBuild, parentRelationship,
                                condensed}: BuildSummaryProps) => {
  const accessor = useDataAccessor([build.id]);
  const now = useCurrentTime();

  const propertiesQuery = useDataApiQuery(() => build.getProperties());
  const stepsQuery = useDataApiQuery(() => build.getSteps());
  const builderQuery = useDataApiQuery(() => Builder.getAll(accessor, {id: build.builderid.toString()}));
  const builderBuilderQuery = useDataApiDynamicQuery([parentBuild !== null],
    () => parentBuild === null
      ? new DataCollection<Builder>()
      : Builder.getAll(accessor, {id: parentBuild.builderid.toString()}));
  const logsQuery = useDataApiQuery(() => stepsQuery.getRelated(step => step.getLogs()));

  const [detailLevel, setDetailLevel] =
    useState<DetailLevel>(condensed ? DetailLevel.None : DetailLevel.Everything);

  const builder = builderQuery.getNthOrNull(0);
  const parentBuilder = builderBuilderQuery.getNthOrNull(0);
  const stepsToDisplay = stepsQuery.array.filter(step => isStepDisplayed(step, detailLevel));

  const reason = getPropertyValueOrDefault(propertiesQuery.properties, "reason", null);

  // FIXME: implement trigger URL pagination

  const [fullDisplay, setFullDisplay] = useState(false);

  const toggleDetails = () => {
    setDetailLevel(level => (level + 1) % DetailLevel.Count);
  };

  const renderParentBuildLink = () => {
    if (parentBuild === null || parentBuilder === null) {
      return <></>
    }

    const relationship = parentRelationship === null ? "" : parentRelationship;
    return (
      <span>
        <Link to={`/builders/${parentBuild.builderid}/builds/${parentBuild.number}`}>
          <BadgeStatus className={results2class(parentBuild, null)}>
            <>{relationship}:{parentBuilder.name}/{parentBuild.number}</>
          </BadgeStatus>
        </Link>
      </span>
    );
  }

  const stepElements = stepsToDisplay.map(step => (
    <BuildSummaryStepLine key={step.id} build={build} step={step}
                          logs={logsQuery.getParentCollectionOrEmpty(step.id)}
                          parentFullDisplay={fullDisplay}/>
  ));

  return (
    <Card className={"bb-build-summary " + results2class(build, null)}>
      <Card.Header>
        <div onClick={() => setFullDisplay(!fullDisplay)} title="Expand all step logs"
             className="btn btn-xs btn-default">
          <ArrowExpander isExpanded={fullDisplay}/>
        </div>
        <div onClick={toggleDetails} title="Show steps according to their importance"
             className="btn btn-xs btn-default">
          <i className="fa fa-expand"></i>
          {detailLevelToString(detailLevel)}
        </div>
        { builder !== null
          ? <Link to={`/builders/${build.builderid}/builds/${build.number}`}>
              &nbsp;
              {builder.name}/{build.number}
            </Link>
          : <></>
        }
        {reason !== null ? <span>| {reason}</span> : <></>}
        <div className={"bb-build-summary-details"}>
          {
            build.complete
              ? <span>{durationFormat(build.complete_at! - build.started_at)}&nbsp;</span>
              : <span>{durationFormat(now - build.started_at)}&nbsp;</span>
          }
          <span>{build.state_string}&nbsp;</span>
          <BadgeStatus className={results2class(build, null)}>{results2text(build)}</BadgeStatus>
          {renderParentBuildLink()}
        </div>
      </Card.Header>
      <ul className="list-group">
        {stepElements}
      </ul>
    </Card>
  );
});

export default BuildSummary;
