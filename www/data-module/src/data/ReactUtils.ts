/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {createContext, useContext, useEffect, useRef} from "react";
import {DataClient} from "./DataClient";
import {IDataAccessor} from "./DataAccessor";
import {DataCollection, IDataCollection} from "./DataCollection";
import {IObservableArray} from "mobx";
import {BaseClass} from "./classes/BaseClass";
import {DataPropertiesCollection} from "./DataPropertiesCollection";

// The default value is not used as the context is injected
export const DataClientContext = createContext<DataClient>(undefined as any);

export function useDataAccessor<T>(dependency: any[]): IDataAccessor {
  const dataClient = useContext(DataClientContext);

  const storedDependency = useRef<any[]>([]);
  const accessor= useRef<IDataAccessor|null>(null);

  if (accessor.current === null) {
    accessor.current = dataClient.open();
    storedDependency.current = [...dependency];
  } else if (!arrayElementsEqual(dependency, storedDependency.current)) {
    accessor.current.close();
    accessor.current = dataClient.open();
    storedDependency.current = [...dependency];
  }

  useEffect(() => {
    if (accessor.current !== null) {
      return () => {
        accessor.current!.close();
        accessor.current = null;
      }
    }
  }, []);

  return accessor.current;
}

export function useDataApiQuery<Collection extends IDataCollection>(
    callback: () => Collection): Collection {
  let storedCollection = useRef<Collection|null>(null);
  if (storedCollection.current === null || !storedCollection.current.isValid()) {
    if (storedCollection.current !== null) {
      storedCollection.current.close();
    }
    storedCollection.current = callback();
  }
  return storedCollection.current;
}

function arrayElementsEqual<T>(a: any[], b: any[]) {
  if (a.length !== b.length) {
    return false;
  }
  for (let i = 0; i < a.length; ++i) {
    if (a[i] !== b[i]) {
      return false;
    }
  }
  return true;
}

export function useDataApiDynamicQuery<T, Collection extends IDataCollection>(
    dependency: any[], callback: () => Collection): Collection {
  const storedDependency = useRef<any[]>([]);
  let storedCollection = useRef<Collection|null>(null);

  if (storedCollection.current === null ||
      !storedCollection.current.isValid() ||
      !arrayElementsEqual(dependency, storedDependency.current)) {
    if (storedCollection.current !== null) {
      storedCollection.current.close();
    }
    storedCollection.current = callback();
    storedDependency.current = [...dependency];
  }

  return storedCollection.current;
}

// The difference between this function and useDataApiDynamicQuery() is that
// useDataApiDynamicQuery() will return empty collection whenever it is refreshed whereas
// this function will wait until the replacement query is resolved.
export function useDataApiDynamicQueryResolved<T, Collection extends IDataCollection>(
  dependency: any[], callback: () => Collection): Collection {
  const storedDependency = useRef<any[]>([]);
  let storedCollection = useRef<Collection|null>(null);
  let storedNewCollection = useRef<Collection|null>(null);

  if (storedCollection.current === null ||
      !storedCollection.current.isValid() ||
      !arrayElementsEqual(dependency, storedDependency.current)) {

    if (storedCollection.current !== null) {
      if (storedNewCollection.current !== null) {
        storedNewCollection.current.close();
      }
      storedNewCollection.current = callback();
    } else {
      storedCollection.current = callback();
    }
    storedDependency.current = [...dependency];
  } else if (storedNewCollection.current !== null && storedNewCollection.current.isResolved()) {
    if (storedCollection.current !== null) {
      storedCollection.current.close();
    }
    storedCollection.current = storedNewCollection.current;
    storedNewCollection.current = null;
  }

  return storedCollection.current;
}

export function useDataApiSingleElementQuery<T extends BaseClass, U extends BaseClass>(
    el: T | null, dependencies: any[], callback: (el: T) => DataCollection<U>): DataCollection<U> {
  return useDataApiDynamicQuery([el === null, ...dependencies],
    () => el === null ? new DataCollection<U>() : callback(el));
}

export function useDataApiSinglePropertiesQuery<T extends BaseClass>(
  el: T | null, dependencies: any[], callback: (el: T) => DataPropertiesCollection): DataPropertiesCollection {
  return useDataApiDynamicQuery([el === null, ...dependencies],
    () => el === null ? new DataPropertiesCollection() : callback(el));
}

export function findOrNull<T>(array: IObservableArray<T>, filter: (el: T) => boolean): T | null {
  for (const el of array) {
    if (filter(el)) {
      return el;
    }
  }
  return null;
}
