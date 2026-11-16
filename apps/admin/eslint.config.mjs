import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    // Ley 1581: el apodo de un menor no llega a las vistas admin. Ninguna
    // fuente de la consola lo lee, ni con punto ni con corchetes ni
    // desestructurado.
    files: ["src/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector: "MemberExpression[property.name='apodo'], MemberExpression[property.value='apodo']",
          message: "El admin no lee el apodo de un menor (Ley 1581).",
        },
        {
          selector: "ObjectPattern > Property[key.name='apodo']",
          message: "El admin no lee el apodo de un menor (Ley 1581).",
        },
      ],
    },
  },
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts"]),
]);

export default eslintConfig;
