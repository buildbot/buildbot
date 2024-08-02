/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/


import {action, makeObservable, observable} from "mobx";
import {BaseClass} from "./BaseClass";
import {IDataDescriptor} from "./DataDescriptor";
import {IDataAccessor} from "../DataAccessor";

export class TestResult extends BaseClass {
  @observable test_resultid!: number;
  @observable builderid!: number;
  @observable test_result_setid!: number;
  @observable test_name!: string|null;
  @observable test_code_path!: string|null;
  @observable duration_ns!: number|null;
  @observable line!: number|null;
  @observable value!: string;

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.test_resultid));
    this.update(object);
    makeObservable(this);
  }

  @action update(object: any) {
    this.test_resultid = object.test_resultid;
    this.builderid = object.builderid;
    this.test_result_setid = object.test_result_setid;
    this.test_name = object.test_name;
    this.test_code_path = object.test_code_path;
    this.duration_ns = object.duration_ns;
    this.line = object.line;
    this.value = object.value;
  }

  toObject() {
    return {
      test_resultid: this.test_resultid,
      builderid: this.builderid,
      test_result_setid: this.test_result_setid,
      test_name: this.test_name,
      test_code_path: this.test_code_path,
      duration_ns: this.duration_ns,
      line: this.line,
      value: this.value,
    };
  }
}

export class TestResultDescriptor implements IDataDescriptor<TestResult> {
  restArrayField = "test_results";
  fieldId: string = "test_resultid";

  parse(accessor: IDataAccessor, endpoint: string, object: any) {
    return new TestResult(accessor, endpoint, object);
  }
}

export const testResultDescriptor = new TestResultDescriptor();
