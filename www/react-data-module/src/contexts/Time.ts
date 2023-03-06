/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {createContext} from "react";
import TimeStore from "../stores/TimeStore";

export const TimeContext = createContext<TimeStore>(undefined as any);
