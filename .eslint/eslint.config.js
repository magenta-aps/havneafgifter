// https://eslint.org/docs/latest/use/configure/
// eslint.config.js
import js from "@eslint/js";
import globals from "globals";

export default [
    js.configs.recommended,
    {
        languageOptions: {
            globals: {
                ...globals.browser,
                commonjs: true,
                es6: true,
                jquery: true,
            },
            ecmaVersion: 6,
            sourceType: "script",
        },
        rules: {
            "no-case-declarations": "off",
        }
    }
];
