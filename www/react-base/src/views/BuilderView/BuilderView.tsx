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

import {observer} from "mobx-react";
import {useContext, useState} from "react";
import {useDataAccessor, useDataApiQuery} from "../../data/ReactUtils";
import {globalRoutes} from "../../plugins/GlobalRoutes";
import {Build} from "../../data/classes/Build";
import {Builder} from "../../data/classes/Builder";
import {useTopbarItems} from "../../stores/TopbarStore";
import {StoresContext} from "../../contexts/Stores";
import {Buildrequest} from "../../data/classes/Buildrequest";
import BuildsTable from "../../components/BuildsTable/BuildsTable";
import BuildRequestsTable from "../../components/BuildrequestsTable/BuildrequestsTable";
import {Forcescheduler} from "../../data/classes/Forcescheduler";
import {TopbarAction} from "../../components/TopbarActions/TopbarActions";
import {useTopbarActions} from "../../stores/TopbarActionsStore";
import {useNavigate, useParams} from "react-router-dom";
import DataCollection from "../../data/DataCollection";
import AlertNotification from "../../components/AlertNotification/AlertNotification";
import ForceBuildModal from "../../components/ForceBuildModal/ForceBuildModal";
import TableHeading from "../../components/TableHeading/TableHeading";

const anyCancellableBuilds = (builds: DataCollection<Build>,
                              buildrequests: DataCollection<Buildrequest>) => {
  let cancellable = false;
  for (const build of builds.array) {
    if (!build.complete) {
      cancellable = true;
    }
  }
  for (const buildrequest of buildrequests.array) {
    if (!buildrequest.claimed) {
      cancellable = true;
    }
  }
  return cancellable;
}

const buildTopbarActions = (builds: DataCollection<Build>,
                            buildrequests: DataCollection<Buildrequest>,
                            forceschedulers: DataCollection<Forcescheduler>,
                            isCancelling: boolean,
                            cancelWholeQueue: () => void,
                            invokeScheduler: (sch: Forcescheduler) => void) => {
  const actions: TopbarAction[] = [];

  if (anyCancellableBuilds(builds, buildrequests)) {
    if (isCancelling) {
      actions.push({
        caption: "Cancelling...",
        icon: "spinner fa-spin",
        action: cancelWholeQueue
      });
    } else {
      actions.push({
        caption: "Cancel whole queue",
        variant: "danger",
        icon: "stop",
        action: cancelWholeQueue
      });
    }
  }

  for (const sch of forceschedulers.array) {
    actions.push({
      caption: sch.button_name,
      variant: "primary",
      action: () => { invokeScheduler(sch); }
    });
  }

  return actions;
}

const BuilderView = observer(() => {
  const builderid = Number.parseInt(useParams<"builderid">().builderid ?? "");
  const navigate = useNavigate();

  const stores = useContext(StoresContext);
  const accessor = useDataAccessor([builderid]);

  const numBuilds = 200;

  const buildersQuery = useDataApiQuery(() => Builder.getAll(accessor, {id: builderid.toString()}));
  const buildsQuery = useDataApiQuery(() =>
    buildersQuery.getRelated(builder => Build.getAll(accessor, {query: {
        builderid: builder.builderid,
        property: ["owners", "workername", "branch"],
        limit: numBuilds,
        order: '-number'
      }
    })));
  const buildrequestsQuery = useDataApiQuery(() =>
    buildersQuery.getRelated(builder => Buildrequest.getAll(accessor, {query: {
        builderid: builder.builderid,
        claimed: false
      }
    })));
  const forceSchedulersQuery = useDataApiQuery(() =>
    buildersQuery.getRelated(builder => builder.getForceschedulers({query: {order: "name"}})));

  const builder = buildersQuery.getNthOrNull(0);
  const builds = buildsQuery.getParentCollectionOrEmpty(builderid.toString());
  const buildrequests = buildrequestsQuery.getParentCollectionOrEmpty(builderid.toString());
  const forceschedulers = forceSchedulersQuery.getParentCollectionOrEmpty(builderid.toString());

  const [isCancelling, setIsCancelling] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useTopbarItems(stores.topbar, builder === null ? [] : [
    {caption: "Builders", route: "/builders"},
    {caption: builder.name, route: `/builders/${builderid}`},
  ]);

  const cancelWholeQueue = () => {
    if (isCancelling) {
      return;
    }
    if (!window.confirm("Are you sure you want to cancel all builds?")) {
      return;
    }
    setIsCancelling(true);

    const dl: Promise<void>[] = [];
    for (const buildrequest of buildrequests.array) {
      if (!buildrequest.claimed) {
        dl.push(buildrequest.control('cancel'));
      }
    }
    for (const build of builds.array) {
      if (!build.complete) {
        dl.push(build.control('stop'));
      }
    }
    Promise.all(dl).then(() => {
      setIsCancelling(false);
    }, (reason) => {
      setIsCancelling(false);
      setErrorMsg(`Cannot cancel: ${reason.error.message}`);
    })
  };

  const [shownForceScheduler, setShownForceScheduler] = useState<null|Forcescheduler>(null);

  const actions = buildTopbarActions(builds, buildrequests, forceschedulers, isCancelling,
    cancelWholeQueue, (sch) => setShownForceScheduler(sch));

  useTopbarActions(stores.topbarActions, actions);

  const onForceBuildModalClose = (buildRequestNumber: string | null) => {
    if (buildRequestNumber === null) {
      setShownForceScheduler(null);
    } else {
      navigate(`/buildrequests/${buildRequestNumber}?redirect_to_build=true`);
    }
  };

  return (
    <div className="container">
      <AlertNotification text={errorMsg}/>
      {builder !== null && builder.description !== null
        ? <div><TableHeading>Description:</TableHeading>{builder.description}</div>
        : <></>
      }
      <BuildRequestsTable buildrequests={buildrequests}/>
      <BuildsTable builds={builds} builders={null}/>
      {shownForceScheduler !== null
        ? <ForceBuildModal scheduler={shownForceScheduler} builderid={builderid}
                           onClose={onForceBuildModalClose}/>
        : <></>
      }
    </div>
  );
  // TODO: reimplement build duration tab
  // TODO: display more than 100 builds
});

globalRoutes.addRoute({
  route: "builders/:builderid",
  group: null,
  element: () => <BuilderView/>,
});

export default BuilderView;
