/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import moment from "moment";
import {useContext, useEffect} from "react";
import {TimeContext} from "../contexts/Time";

export function durationFormat(time: number) {
  if (time < 0) {
    return "";
  }

  const d = moment.duration(time * 1000);
  const m = moment.utc(d.asMilliseconds());
  const days = Math.floor(d.asDays());
  if (days) {
    let plural = "";
    if (days > 1) {
      plural = "s";
    }
    return `${days} day${plural} ` + m.format('H:mm:ss');
  }
  if (d.hours()) {
    return m.format('H:mm:ss');
  }
  if (d.minutes()) {
    return m.format('m:ss');
  } else {
    return m.format('s') + " s";
  }
}

export function dateFormat(time: number) {
  return moment.unix(time).format('LLL');
}

export function durationFromNowFormat(time: number, now: number) {
  return moment.unix(time).from(moment.unix(now), false);
}

export function useCurrentTime() {
  const timeStore = useContext(TimeContext);
  return timeStore.now;
}

export function useCurrentTimeSetupTimers() {
  const timeStore = useContext(TimeContext);
  useEffect(() => {
    const timer = setInterval(
      () => timeStore.setTime(moment().unix()),
      1000
    );
    return () => clearInterval(timer);

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
