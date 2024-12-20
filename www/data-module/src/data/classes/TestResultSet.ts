/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/


import {action, makeObservable, observable} from "mobx";
import {BaseClass} from "./BaseClass";
import {IDataDescriptor} from "./DataDescriptor";
import {IDataAccessor} from "../DataAccessor";
import {RequestQuery} from "../DataQuery";
import {TestResult, testResultDescriptor} from "./TestResult";


export class TestResultSet extends BaseClass {
  @observable test_result_setid!: number;
  @observable builderid!: number;
  @observable buildid!: number;
  @observable stepid!: number;
  @observable description!: string;
  @observable category!: string;
  @observable value_unit!: string;
  @observable tests_passed!: number|null;
  @observable tests_failed!: number|null;
  @observable complete!: boolean;

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.test_result_setid));
    this.update(object);
    makeObservable(this);
  }

  @action update(object: any) {
    this.test_result_setid = object.test_result_setid;
    this.builderid = object.builderid;
    this.buildid = object.buildid;
    this.stepid = object.stepid;
    this.description = object.description;
    this.category = object.category;
    this.value_unit = object.value_unit;
    this.tests_passed = object.tests_passed;
    this.tests_failed = object.tests_failed;
    this.complete = object.complete;
  }

  toObject() {
    return {
      test_result_setid: this.test_result_setid,
      builderid: this.builderid,
      buildid: this.buildid,
      stepid: this.stepid,
      description: this.description,
      category: this.category,
      value_unit: this.value_unit,
      tests_passed: this.tests_passed,
      tests_failed: this.tests_failed,
      complete: this.complete,
    }
  }

  getResults(query: RequestQuery = {}) {
    return this.get<TestResult>("results", query, testResultDescriptor);
  }

  static getAll(accessor: IDataAccessor, query: RequestQuery = {}) {
    return accessor.get<TestResultSet>("test_result_sets", query, testResultSetDescriptor);
  }
}

export class TestResultSetDescriptor implements IDataDescriptor<TestResultSet> {
  restArrayField = "test_result_sets";
  fieldId: string = "test_result_setid";

  parse(accessor: IDataAccessor, endpoint: string, object: any) {
    return new TestResultSet(accessor, endpoint, object);
  }
}

export const testResultSetDescriptor = new TestResultSetDescriptor();
