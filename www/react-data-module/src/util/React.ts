/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {Dispatch, SetStateAction, useState} from "react";

export function useStateWithDefaultIfNotSet<T>(
    defaultCallback: () => T): [T, Dispatch<SetStateAction<T|null>>] {
  const [explicitValue, setValue] = useState<T | null>(null);
  const value: T = explicitValue !== null ? explicitValue : defaultCallback();
  return [value, setValue];
}

// Just like useStateWithDefaultIfNotSet, however the current state is changed whenever a given
// "parent" state is changed. The current state can otherwise be changed independently
export function useStateWithParentTrackingWithDefaultIfNotSet<T>(
    parentValue: T, defaultCallback: () => T): [T, (v: T) => void] {
  const [lastParentValue, setLastParentValue] = useState(parentValue);
  const [explicitValue, setExplicitValue] = useState<T | null>(null);

  if (parentValue !== lastParentValue) {
    setLastParentValue(parentValue);
    setExplicitValue(parentValue);
    return [parentValue, t => setExplicitValue(t)];
  }

  const value: T = explicitValue !== null ? explicitValue : defaultCallback();
  return [value, t => setExplicitValue(t)];
}
