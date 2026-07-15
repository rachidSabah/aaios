import tseslint from 'typescript-eslint';

export default tseslint.config(
  {
    ignores: ['node_modules/**', '.next/**'],
  },
  ...tseslint.configs.recommended,
  {
    rules: {
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': 'warn',
      '@typescript-eslint/no-explicit-any': 'off',
    },
  },
);
