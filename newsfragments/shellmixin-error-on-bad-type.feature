Added check for correct argument types to `BuildStep` and `ShellCommand` build steps and all steps
deriving from `ShellMixin`. This will avoid wrong arguments causing confusing errors in unrelated
parts of the codebase.
