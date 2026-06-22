import jsdoc from "eslint-plugin-jsdoc";

export default [
  {
    files: ["src/footballd3/**/*.js"],
    languageOptions: { ecmaVersion: "latest", sourceType: "module" },
    plugins: { jsdoc },
    rules: {
      "jsdoc/require-jsdoc": ["error", {
        publicOnly: true,
        require: { FunctionDeclaration: true, ArrowFunctionExpression: true, FunctionExpression: true }
      }],
      "jsdoc/require-param": "error",
      "jsdoc/require-returns": "error",
      "jsdoc/require-description": "error"
    }
  }
];