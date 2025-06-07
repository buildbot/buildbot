import { defineConfig } from "eslint/config";
import {buildbotEslintConfig} from "build-config-buildbot";

export default defineConfig([
  {
    extends: [buildbotEslintConfig],
  },
]);
