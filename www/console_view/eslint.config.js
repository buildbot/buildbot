import { defineConfig } from "eslint/config";
import buildbotConfig from "eslint-config-buildbot";

export default defineConfig([
  {
    extends: [buildbotConfig],
  },
]);
