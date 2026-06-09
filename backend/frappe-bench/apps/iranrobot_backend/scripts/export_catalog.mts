// Export the IranRobot frontend catalog (robots.ts + categories.ts) to a JSON snapshot.
//
// Reads:
//   ../iranrobot/src/data/robots.ts     (ROBOTS array)
//   ../iranrobot/src/data/categories.ts (PLP_CATEGORIES array)
//
// Writes:
//   ../data/catalog_snapshot.json
//
// Run from the iranrobot_backend repo root:
//   npx --yes tsx scripts/export_catalog.mts
//
// The .mts extension + tsx loader handles TypeScript + ESM resolution.

import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { ROBOTS } from "../../iranrobot/src/data/robots.ts";
import { PLP_CATEGORIES } from "../../iranrobot/src/data/categories.ts";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// PlpCategory.match is a function -- not JSON-serializable. Strip it.
const categoriesForJson = PLP_CATEGORIES.map((c) => {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { match, ...rest } = c;
  return rest;
});

const snapshot = {
  exportedAt: new Date().toISOString(),
  source: "iranrobot/src/data/robots.ts + categories.ts",
  productCount: ROBOTS.length,
  categoryCount: categoriesForJson.length,
  products: ROBOTS,
  plpCategories: categoriesForJson,
};

const outPath = resolve(__dirname, "..", "data", "catalog_snapshot.json");
mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, JSON.stringify(snapshot, null, 2), "utf8");

console.log(
  `Wrote ${outPath}\n  products:    ${ROBOTS.length}\n  plp cats:    ${categoriesForJson.length}`,
);
