// Draws the snake with Platane/snk's own engine (npm package generate-snake-animation),
// but feeds it calendar.json from snake_calendar.py instead of GitHub's calendar.
//
// usage: SNK_LIB=<path to generate-snake-animation/generateSnakeAnimation.js> node snake.mjs calendar.json OUT_DIR
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const [calendarPath, outDir] = process.argv.slice(2);
const { generateSnakeAnimation } = await import(pathToFileURL(process.env.SNK_LIB).href);
const calendar = readFileSync(calendarPath, "utf8");

// The npm build does not export snk's palettes, so the two this profile uses are copied from
// packages/generate-snake-animation/palettes.ts ("default" is github-light).
const palettes = {
  default: { colorBackground: "#ffffff", colorDotBorder: "#1b1f230a" },
  "github-dark": { colorBackground: "#0c1116", colorDotBorder: "#1b1f230a" },
};

// The library asks GitHub's GraphQL API for the calendar; answer with ours instead.
globalThis.fetch = async () =>
  new Response(calendar, { status: 200, headers: { "content-type": "application/json" } });

// Same options as the Platane/snk action builds from "?palette=…&color_snake=…&color_dots=…".
const svg = (palette, colorDots) => ({
  format: "svg",
  drawOptions: {
    sizeDotBorderRadius: 2,
    sizeCell: 16,
    sizeDot: 12,
    ...palettes["default"],
    ...(palette ? palettes[palette] : {}),
    colorDots,
    colorEmpty: colorDots[0],
    colorSnake: "#ff2e88",
  },
  animationOptions: { frameByStep: 1, stepDurationMs: 100 },
});

const outputs = {
  "snake.svg": svg(null, ["#ebedf0", "#c6c2ca", "#8d8794", "#4a4550", "#0b0b0f"]),
  "snake-dark.svg": svg("github-dark", ["#161b22", "#2e2a33", "#4e4856", "#857e8e", "#c9c2cf"]),
};

const results = await generateSnakeAnimation(
  { platform: "github", username: "calendar.json", githubToken: "unused" },
  Object.values(outputs),
);
mkdirSync(outDir, { recursive: true });
Object.keys(outputs).forEach((name, i) => writeFileSync(join(outDir, name), results[i]));
console.log(`snake written to ${outDir}`);
