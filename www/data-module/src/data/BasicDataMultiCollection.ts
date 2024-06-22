/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {BaseClass} from "./classes/BaseClass";
import {
  action,
  autorun,
  IObservableArray,
  makeObservable,
  observable,
  ObservableMap
} from "mobx";
import {DataCollection, IDataCollection} from "./DataCollection";
import {IReactionDisposer} from "mobx";
import {IDataAccessor} from "./DataAccessor";

/* This class wraps multiple DataCollections of the same thing.
 */
export class BasicDataMultiCollection<ParentDataType extends BaseClass,
  Collection extends IDataCollection> implements IDataCollection {

  accessor: IDataAccessor;
  parentArray: IObservableArray<ParentDataType> | null;
  parentArrayMap: ObservableMap<string, DataCollection<ParentDataType>> | null;
  parentFilteredIds: IObservableArray<string> | null;

  @observable byParentId = observable.map<string, Collection>();
  @observable sortedParentIds = observable.array<string>();
  callback: (parent: ParentDataType) => Collection;
  private disposer: IReactionDisposer;

  constructor(accessor: IDataAccessor,
              parentArray: IObservableArray<ParentDataType> | null,
              parentArrayMap: ObservableMap<string, DataCollection<ParentDataType>> | null,
              parentFilteredIds: IObservableArray<string> | null,
              callback: (parent: ParentDataType) => Collection) {
    makeObservable(this);

    this.accessor = accessor;
    this.parentArray = parentArray;
    this.parentArrayMap = parentArrayMap;
    this.parentFilteredIds = parentFilteredIds;

    this.callback = callback;
    if (parentArray !== null) {
      this.disposer = autorun(() => {
        const newParentIds = new Set<string>();
        for (let parent of this.parentArray!) {
          if (this.parentFilteredIds !== null && this.parentFilteredIds.indexOf(parent.id) < 0) {
            continue;
          }

          newParentIds.add(parent.id);
          if (!this.byParentId.has(parent.id)) {
            this.addByParentId(parent.id, this.callback(parent));
          }
        }

        for (let key of this.byParentId.keys()) {
          if (!newParentIds.has(key)) {
            this.removeByParentId(key);
          }
        }
      });
    } else if (parentArrayMap !== null) {
      this.disposer = autorun(() => {
        const newParentIds = new Set<string>();
        for (const parentList of this.parentArrayMap!.values()) {
          for (const parent of parentList.array) {
            if (this.parentFilteredIds !== null && this.parentFilteredIds.indexOf(parent.id) < 0) {
              continue;
            }

            newParentIds.add(parent.id);
            if (!this.byParentId.has(parent.id)) {
              this.addByParentId(parent.id, this.callback(parent));
            }
          }
        }
        for (let key of this.byParentId.keys()) {
          if (!newParentIds.has(key)) {
            this.removeByParentId(key);
          }
        }
      });
    } else {
      throw Error("Either parentArray or parentArrayMap must not be null");
    }
  }

  isValid() {
    if (this.accessor === undefined) {
      return false;
    }
    return this.accessor.isOpen();
  }

  isResolved() {
    let resolved = true;
    for (const collection of this.byParentId.values()) {
      resolved = resolved && collection.isResolved();
    }
    return resolved;
  }

  subscribe() {
    return Promise.resolve();
  }

  initial(data: any[]) {}

  close() : Promise<void> {
    this.disposer();
    return Promise.all([...this.byParentId.values()].map((collection => collection.close()))).then();
  }

  @action addByParentId(id: string, collection: Collection) {
    this.byParentId.set(id, collection);
    this.sortedParentIds.push(id);
    this.sortedParentIds.sort();
  }

  @action removeByParentId(id: string) {
    this.byParentId.get(id)?.close();
    this.byParentId.delete(id);
    this.sortedParentIds.remove(id);
  }
}
