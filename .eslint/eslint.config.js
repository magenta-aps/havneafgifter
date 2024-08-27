// https://eslint.org/docs/latest/use/configure/
// eslint.config.js
import js from "@eslint/js";
import globals from "globals";

export default [
    js.configs.recommended,
    {
        languageOptions: {
            globals: {
                ...globals.browser
            },
            ecmaVersion: 6,
            sourceType: "script",
        },
        env: {
            browser: true,
            commonjs: true,
            es6: true,
            jquery: true
        },
        rules: {
            "no-case-declarations": "off",
        }
    }
];
