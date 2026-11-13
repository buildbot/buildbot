import globals from 'globals'
import reactPlugin from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'
import {reactRefresh} from 'eslint-plugin-react-refresh'
import importPlugin from 'eslint-plugin-import';
import jsxAlly from 'eslint-plugin-jsx-a11y'
import tseslint from 'typescript-eslint'

export const buildbotEslintConfig = tseslint.config(
  { ignores: ['dist'] },
  {
    extends: [
      ...tseslint.configs.recommendedTypeChecked,
      reactPlugin.configs.flat['jsx-runtime'],
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite({extraHOCs: ['observer']}),
      importPlugin.flatConfigs.recommended,
      importPlugin.flatConfigs.typescript,
      jsxAlly.flatConfigs.recommended,
    ],
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-unsafe-argument': 'off',
      '@typescript-eslint/no-unsafe-assignment': 'off',
      '@typescript-eslint/no-unsafe-call': 'off',
      '@typescript-eslint/no-unsafe-function-type': 'off',
      '@typescript-eslint/no-unsafe-member-access': 'off',
      '@typescript-eslint/no-unsafe-return': 'off',
      // eslint-plugin-import: tsc already checks these
      'import/no-unresolved': 'off',
      'import/namespace': 'off',
      'import/default': 'off',
      '@typescript-eslint/no-unused-vars': [
        "warn",
        {
          "argsIgnorePattern": "^_",
          "varsIgnorePattern": "^_",
          "caughtErrorsIgnorePattern": "^_"
        }
      ],
    },
  },
)

export const buildbotPrettierConfig = {
  tabWidth: 2,
  printWidth: 100,
  singleQuote: true,
  trailingComma: 'all',
  bracketSpacing: false,
  bracketSameLine: false,
  arrowParens: 'always',
}