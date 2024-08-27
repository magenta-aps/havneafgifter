// https://eslint.org/docs/latest/use/configure/
// eslint.config.js
import js from "@eslint/js";
import globals from "globals";

export default [
    {
        languageOptions: {
            globals: {
                ...globals.browser,
                commonjs: true,
                es6: true,
                jquery: true,
                $: 'readonly',
                bootstrap: 'readonly',
                tempusDominus: 'readonly',
            },
            ecmaVersion: "latest",
            sourceType: "module",
        },
        rules: {
            "no-case-declarations": "off",
            "no-global-assign": "off",
        }
    },
];
