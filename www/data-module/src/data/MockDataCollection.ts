/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {action} from "mobx";
import {BaseClass} from "./classes/BaseClass";
import {DataCollection} from "./DataCollection";

/** A simplified wrapper around DataCollection that is useful in tests.
    No query filtering is done, the test data must be already in correct order and have correct
    items according to the query used in the code under test.
 */
export class MockDataCollection<DataType extends BaseClass> extends DataCollection<DataType> {
  @action setItems(items: DataType[]) {
    this.resolved = true;
    for (const item of items) {
      this.byId.set(item.id, item);
      this.array.push(item);
    }
  }
}
