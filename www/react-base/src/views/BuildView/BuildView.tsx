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

import './BuildView.scss';
import {observer} from "mobx-react";
import {FaSpinner} from "react-icons/fa";
import {AlertNotification} from "../../components/AlertNotification/AlertNotification";
import {useEffect, useState} from "react";
import {Link, NavigateFunction, useNavigate, useParams} from "react-router-dom";
import {buildbotSetupPlugin} from "buildbot-plugin-support";
import {
  Build,
  Buildrequest,
  Buildset,
  Builder,
  Change,
  DataCollection,
  DataPropertiesCollection,
  Project,
  Worker,
  UNKNOWN,
  findOrNull,
  getPropertyValueOrDefault,
  getBuildOrStepResults,
  parseChangeAuthorNameAndEmail,
  results2class,
  useDataAccessor,
  useDataApiDynamicQuery,
  useDataApiQuery,
  useDataApiSingleElementQuery,
} from "buildbot-data-js";
import {computed} from "mobx";
import {
  BadgeRound,
  ChangeUserAvatar,
  TopbarAction,
  dateFormat,
  durationFromNowFormat,
  useCurrentTime,
  useFavIcon,
  useTopbarItems,
  useTopbarActions,
} from "buildbot-ui";
import {PropertiesTable} from "../../components/PropertiesTable/PropertiesTable";
import {ChangesTable} from "../../components/ChangesTable/ChangesTable";
import {BuildSummary} from "../../components/BuildSummary/BuildSummary";
import {Tab, Table, Tabs} from "react-bootstrap";
import {buildTopbarItemsForBuilder} from "../../util/TopbarUtils";
import {BuildViewDebugTab} from "./BuildViewDebugTab";

const buildTopbarActions = (
  build: Build | null,
  isRebuilding: boolean, rebuiltBuildRequest: Buildrequest | null,
  isStopping: boolean,
  doRebuild: () => void, doStop: () => void,
  navigate: NavigateFunction,
) => {
  const actions: TopbarAction[] = [];
  if (build === null) {
    return actions;
  }

  if (build.complete) {
    if (rebuiltBuildRequest !== null) {
      const caption = rebuiltBuildRequest.complete ? "Rebuilt" : (rebuiltBuildRequest.claimed ? "Rebuilding..." : "Rebuild pending");
      actions.push({
        caption: caption,
        icon: (rebuiltBuildRequest.complete ? undefined : <FaSpinner />),
        action: () => {
          navigate(`/buildrequests/${rebuiltBuildRequest.id}?redirect_to_build=true`);
        }
      })
    }
    else if (isRebuilding) {
      actions.push({
        caption: "Rebuilding...",
        icon: <FaSpinner />,
        // do nothing, wait for 'rebuiltBuildRequest'
        action: () => { },
      });
    } else {
      actions.push({
        caption: "Rebuild",
        action: doRebuild
      });
    }
  } else {
    if (isStopping) {
      actions.push({
        caption: "Stopping...",
        icon: <FaSpinner/>,
        action: doStop
      });
    } else {
      actions.push({
        caption: "Stop",
        action: doStop
      });
    }
  }
  return actions;
}

const getResponsibleUsers = (propertiesQuery: DataPropertiesCollection,
                             changesQuery: DataCollection<Change>) => {
  const responsibleUsers: {[name: string]: string | null} = {};
  if (getPropertyValueOrDefault(propertiesQuery.properties, "scheduler", "") === "force") {
    const owner = getPropertyValueOrDefault(propertiesQuery.properties, "owner", "");
    if (owner.match(/^.+<.+@.+\..+>.*$/)) {
      const splitResult = owner.split(new RegExp('<|>'));
      if (splitResult.length === 2) {
        const name = splitResult[0];
        const email = splitResult[1];
        responsibleUsers[name] = email;
      }
    }
  }

  for (const change of changesQuery.array) {
    const [name, email] = parseChangeAuthorNameAndEmail(change.author);
    if (email !== null || !(name in responsibleUsers)) {
      responsibleUsers[name] = email;
    }
  }

  return responsibleUsers;
}

const BuildView = observer(() => {
  const builderid = Number.parseInt(useParams<"builderid">().builderid ?? "");
  const buildnumber = Number.parseInt(useParams<"buildnumber">().buildnumber ?? "");
  const navigate = useNavigate();

  const accessor = useDataAccessor([builderid, buildnumber]);

  const buildersQuery = useDataApiQuery(() => Builder.getAll(accessor, {id: builderid.toString()}));
  const builder = buildersQuery.getNthOrNull(0);

  const now = useCurrentTime();

  // get the build plus the previous and next
  // note that this registers to the updates for all the builds for that builder
  // need to see how that scales
  const buildsQuery = useDataApiQuery(() => Build.getAll(accessor, {query: {
        builderid: builderid,
        number__eq: [buildnumber - 1, buildnumber, buildnumber + 1]}
    }));

  const prevBuild = findOrNull(buildsQuery.array, b => b.number === buildnumber - 1);
  const build = findOrNull(buildsQuery.array, b => b.number === buildnumber);
  const nextBuild = findOrNull(buildsQuery.array, b => b.number === buildnumber + 1);

  const changesQuery = useDataApiSingleElementQuery(build, b => b.getChanges());
  const buildrequestsQuery = useDataApiSingleElementQuery(build,
    b => b.buildrequestid === null
      ? new DataCollection<Buildrequest>()
      : Buildrequest.getAll(accessor, {id: b.buildrequestid.toString()}));

  const buildsetsQuery = useDataApiQuery(() => buildrequestsQuery.getRelated(
    br => Buildset.getAll(accessor, {id: br.buildsetid.toString()})));
  const parentBuildQuery = useDataApiQuery(() => buildsetsQuery.getRelated(
    bs => bs.parent_buildid === null
      ? new DataCollection<Build>()
      : Build.getAll(accessor, {id: bs.parent_buildid.toString()})));
  const propertiesQuery = useDataApiDynamicQuery([build === null],
    () => build === null ? new DataPropertiesCollection() : build.getProperties());

  const workersQuery = useDataApiSingleElementQuery(build,
    b => Worker.getAll(accessor, {id: b.workerid.toString()}));

  const projectsQuery = useDataApiQuery(() => buildersQuery.getRelated(builder => {
    return builder.projectid === null
      ? new DataCollection<Project>()
      : Project.getAll(accessor, {id: builder.projectid.toString()})
  }));

  const buildset = buildsetsQuery.getNthOrNull(0);

  // Get rebuilt Build if it exists
  const rebuiltBuildsetQuery = useDataApiDynamicQuery(
    [buildset ?? build],
    () => {
      const rebuilt_buildid = buildset?.rebuilt_buildid ?? build?.buildid;
      if (rebuilt_buildid === undefined) {
        return new DataCollection<Buildset>();
      }
      return Buildset.getAll(
      accessor,
        {
          query: {
            rebuilt_buildid: rebuilt_buildid,
            // don't query the same buildset, use gt as we only want newests
            bsid__gt: buildset !== null ? buildset.bsid : null,
            // only get the most recent one
            // NOTE: this will navigate straight to the newest rebuild
            // we can flip the 'order' here to go to the first rebuild
            limit: 1, order: '-bsid',
          }
        }
      );
    }
  );
  const rebuiltBuildRequestQuery = useDataApiSingleElementQuery(
    rebuiltBuildsetQuery.getNthOrNull(0),
    (bs: Buildset) => Buildrequest.getAll(
      accessor, {
      query: {
        buildsetid: bs.bsid,
        // newest only
        limit: 1, order: '-buildsetid',
      }
    })
  );

  const buildrequest = buildrequestsQuery.getNthOrNull(0);
  const parentBuild = parentBuildQuery.getNthOrNull(0);
  const worker = workersQuery.getNthOrNull(0);
  const project = projectsQuery.getNthOrNull(0);
  const rebuiltBuildRequest = rebuiltBuildRequestQuery.getNthOrNull(0);

  useEffect(() => {
    // note that in case buildsQuery.array was updated, we have to recalculate build value
    const build = findOrNull(buildsQuery.array, b => b.number === buildnumber);
    if (buildsQuery.resolved && build === null) {
      navigate(`/builders/${builderid}`);
    }
  }, [buildsQuery.resolved, build === null]);

  const responsibleUsers = computed(() => getResponsibleUsers(propertiesQuery, changesQuery)).get();
  /*
    $window.document.title = $state.current.data.pageTitle({builder: builder['name'], build: buildnumber});
   */

  const lastBuild = nextBuild === null;

  const [isStopping, setIsStopping] = useState(false);
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const doRebuild = function() {
    setIsRebuilding(true);

    build!.control('rebuild').then((res) => {
      const brid = Object.values(res.result[1])[0];
      navigate(`/buildrequests/${brid}?redirect_to_build=true`);
    }, (reason) => {
      setIsRebuilding(false);
      setErrorMsg(`Cannot rebuild: ${reason.error.message}`);
    });
  };

  const doStop = function() {
    setIsStopping(true);

    build!.control('stop').then(() => {}, (reason) => {
      setIsStopping(false);
      setErrorMsg(`Cannot Stop: ${reason.error.message}`);
    });
  };

  useTopbarItems(buildTopbarItemsForBuilder(builder, project, [
    {caption: buildnumber.toString(), route: `/builders/${builderid}/builds/${buildnumber}`}
  ]));

  const actions = buildTopbarActions(build, isRebuilding, rebuiltBuildRequest, isStopping, doRebuild, doStop, navigate);

  useTopbarActions(actions);
  useFavIcon(getBuildOrStepResults(build, UNKNOWN));

  const renderPager = (build: Build|null) => {
    const renderPrevLink = () => {
      if (buildnumber > 1 && prevBuild !== null && build !== null) {
        return (
          <Link to={`/builders/${builderid}/builds/${prevBuild.number}`}
                className="bb-build-view-nav-button">
            <BadgeRound className={results2class(prevBuild, 'pulse')}>←</BadgeRound>
            <span className="nomobile">&nbsp;Previous</span>
          </Link>
        );
      }
      return (
        <span className="bb-build-view-nav-button">&larr;
          <span className="nomobile">&nbsp;Previous</span>
        </span>
      );
    }

    const renderCompleteTime = () => {
      if (build === null || !build.complete) {
        return <li>&nbsp;</li>;
      }
      return (
        <li title={dateFormat(build.complete_at!)}>
          Finished {durationFromNowFormat(build.complete_at!, now)}
        </li>
      );
    }

    const renderNextLink = () => {
      if (!lastBuild && nextBuild !== null) {
        return (
          <Link to={`/builders/${builderid}/builds/${nextBuild.number}`}
                className="bb-build-view-nav-button">
            <span className="nomobile">Next&nbsp;</span>
            <BadgeRound className={results2class(nextBuild, 'pulse')}>→</BadgeRound>
          </Link>
        )
      }

      return (
        <span className="bb-build-view-nav-button">
          <span className="nomobile">Next&nbsp;</span>
          <span>&rarr;</span>
        </span>
      )
    }

    return (
      <ul className="bb-build-view-pager">
        <li className={"previous " + ((build === null || build.number === 1) ? " disabled" : "")}>
          {renderPrevLink()}
        </li>
        {renderCompleteTime()}
        <li className={"next" + (lastBuild ? " disabled" : "")}>
          {renderNextLink()}
        </li>
      </ul>
    );
  }

  const workerName = worker === null ? "(loading ...)" : worker.name;
  const renderWorkerInfo = () => {
    if (worker === null) {
      return <></>;
    }

    return Object.entries(worker.workerinfo).map(([name, value]) => (
      <tr key={name}>
        <td className="text-left">{name}</td>
        <td className="text-right">{JSON.stringify(value)}</td>
      </tr>
    ));
  }

  const renderResponsibleUsers = () => {
    return Object.entries(responsibleUsers).map(([author, email], index) => (
      <li key={index} className="list-group-item">
        <ChangeUserAvatar name={author} email={email} showName={true}/>
      </li>
    ));
  };

  return (
    <div className="container bb-build-view">
      <AlertNotification text={errorMsg}/>
      <nav>
        {renderPager(build)}
      </nav>
      <Tabs mountOnEnter={true}>
        <Tab eventKey="build-steps" title="Build steps">
          { build !== null
            ? <BuildSummary build={build} condensed={false} parentBuild={parentBuild}
                            parentRelationship={buildset === null ? null : buildset.parent_relationship}/>
            : <></>
          }
        </Tab>
        <Tab eventKey="properties" title="Build Properties">
          <PropertiesTable properties={propertiesQuery.properties}/>
        </Tab>
        <Tab eventKey="worker" title={`Worker: ${workerName}`}>
          <Table hover striped size="sm">
            <tbody>
              <tr>
                <td className="text-left">name</td>
                <td className="text-right">{workerName}</td>
              </tr>
              {renderWorkerInfo()}
            </tbody>
          </Table>
        </Tab>
        <Tab eventKey="responsible" title="Responsible Users">
          <ul className="list-group">
            {renderResponsibleUsers()}
          </ul>
        </Tab>
        <Tab eventKey="changes" title="Changes">
          {build !== null
            ? <ChangesTable changes={changesQuery}/>
            : <></>
          }
        </Tab>
        <Tab eventKey="debug" title="Debug">
          <BuildViewDebugTab build={build} buildrequest={buildrequest} buildset={buildset}/>
        </Tab>
      </Tabs>
    </div>
  );
});

buildbotSetupPlugin((reg) => {
  reg.registerRoute({
    route: "builders/:builderid/builds/:buildnumber",
    group: null,
    element: () => <BuildView/>,
  });

  reg.registerSettingGroup({
    name:'Build',
    caption: 'Build page related settings',
    items:[{
      type: 'integer',
      name: 'trigger_step_page_size',
      caption: 'Number of builds to show per page in trigger step',
      defaultValue: 20
    }, {
      type: 'boolean',
      name: 'show_urls',
      caption: 'Always show URLs in step',
      defaultValue: true
    }
    ]
  });
});
