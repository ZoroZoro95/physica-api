#!/usr/bin/env node
/**
 * Browser render audit for walkthrough/animation sync.
 *
 * This script checks the actual dev page DOM/SVG hooks produced by
 * frontend/app/audit/walkthrough-sync/page.tsx. It intentionally does not
 * judge pixels yet; this is the hard selector layer before screenshot review.
 */

import fs from "node:fs/promises";
import { createRequire } from "node:module";

const args = parseArgs(process.argv.slice(2));
const frontendUrl = args.frontend ?? "http://127.0.0.1:3000";
const apiUrl = args.api ?? "http://127.0.0.1:8000";

async function main() {
  const payload = await loadPayload();
  const probes = payload?.audit?.render_probe_contract?.beat_probes ?? [];
  if (!payload?.animation_scene_spec) {
    throw new Error("Audit payload is missing animation_scene_spec.");
  }
  if (!probes.length) {
    throw new Error("Audit payload has no render probes.");
  }

  const { chromium } = await importPlaywright();
  const browser = await chromium.launch({ headless: args.headed ? false : true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const failures = [];

  try {
    await page.addInitScript(payloadJson => {
      window.sessionStorage.setItem("walkthrough-sync-audit-payload", payloadJson);
    }, JSON.stringify(payload));
    await page.goto(`${frontendUrl.replace(/\/$/, "")}/audit/walkthrough-sync`, { waitUntil: "networkidle" });
    await page.locator("[data-audit-page='walkthrough-sync'][data-audit-client-ready='true']").waitFor({ state: "visible", timeout: 10_000 });
    await page.evaluate(data => {
      window.dispatchEvent(new CustomEvent("walkthrough-sync-audit-payload", {
        detail: { rawJson: JSON.stringify(data), payload: data },
      }));
    }, payload);
    await page.locator("[data-audit-beat-row]").first().waitFor({ state: "visible", timeout: 10_000 });

    const fullLifecycle = page.locator("[data-audit-surface='animation-scene-3d'][data-audit-step-id='__full_lifecycle']");
    if (await fullLifecycle.count() !== 1) {
      failures.push("Full lifecycle 3D audit surface is missing or duplicated.");
    } else {
      const isFull = await fullLifecycle.first().getAttribute("data-audit-full-lifecycle");
      if (isFull !== "true") failures.push("Full lifecycle 3D surface is not marked as full lifecycle.");
    }

    for (const probe of probes) {
      const stepId = String(probe.step_id ?? "");
      if (!probe.requires_render_verification) continue;
      if (!stepId) {
        failures.push("Probe is missing step_id.");
        continue;
      }
      const board = page.locator(`[data-audit-surface='teaching-board-2d'][data-audit-step-id=${JSON.stringify(stepId)}]`);
      const boardCount = await board.count();
      if (boardCount !== 1) {
        failures.push(`${stepId}: expected one teaching board, found ${boardCount}.`);
        continue;
      }

      const visibleVectorIds = csv(await board.first().getAttribute("data-audit-visible-vector-ids"));
      for (const vectorId of probe.expected_vector_ids ?? []) {
        if (!visibleVectorIds.includes(vectorId)) {
          failures.push(`${stepId}: expected visible vector ${vectorId}, got [${visibleVectorIds.join(", ")}].`);
        }
        const vectorCount = await board.locator(`[data-audit-vector-id=${JSON.stringify(vectorId)}]`).count();
        if (vectorCount < 1) {
          failures.push(`${stepId}: vector element ${vectorId} is not rendered.`);
        }
      }

      for (const pointId of probe.expected_point_ids ?? []) {
        const count = await board.locator(`[data-audit-point-id=${JSON.stringify(pointId)}]`).count();
        if (count < 1) failures.push(`${stepId}: highlighted point ${pointId} is not rendered.`);
      }

      for (const surfaceId of probe.expected_surface_ids ?? []) {
        const count = await board.locator(`[data-audit-surface-id=${JSON.stringify(surfaceId)}]`).count();
        if (count < 1) failures.push(`${stepId}: highlighted surface ${surfaceId} is not rendered.`);
      }

      const showTrajectory = await board.first().getAttribute("data-audit-show-trajectory");
      if (Boolean(probe.expected_show_trajectory) !== (showTrajectory === "true")) {
        failures.push(`${stepId}: trajectory visibility expected=${Boolean(probe.expected_show_trajectory)} rendered=${showTrajectory}.`);
      }

      const templateKind = await board.first().getAttribute("data-audit-template-kind");
      const thetaDeg = Number(await board.first().getAttribute("data-audit-template-theta-deg"));
      if (Number.isFinite(thetaDeg)) {
        if (templateKind === "launch-components") {
          await assertTemplateLineAngle({ board, stepId, lineId: "launch-u", expectedDeg: signedAngle(thetaDeg), failures });
        }
        if (templateKind === "descent-components") {
          await assertTemplateLineAngle({ board, stepId, lineId: "descent-u", expectedDeg: -Math.abs(signedAngle(thetaDeg) || 35), failures });
        }
      }
      if (String(templateKind ?? "").startsWith("monkey-hunter-")) {
        await assertRenderedEntity({ board, stepId, entityId: "monkey", failures });
        await assertRenderedEntity({ board, stepId, entityId: "hunter", failures });
        await assertTemplateLineExists({ board, stepId, lineId: "monkey-hunter-aim-line", failures });
      }

      if (args.screenshotDir) {
        await fs.mkdir(args.screenshotDir, { recursive: true });
        const safeStep = stepId.replace(/[^a-z0-9_-]+/gi, "_").slice(0, 80);
        await board.first().screenshot({ path: `${args.screenshotDir}/${safeStep}.png` });
      }
    }
  } finally {
    await browser.close();
  }

  if (failures.length) {
    console.error("Render audit failed:");
    for (const failure of failures) console.error(`- ${failure}`);
    process.exit(1);
  }
  console.log(`Render audit passed: ${probes.length} beat probes checked.`);
}

async function loadPayload() {
  if (args.payload) {
    return JSON.parse(await fs.readFile(args.payload, "utf8"));
  }
  const question = args.question ?? "A ball is thrown at u=16 m/s at 53 deg. Find range and time of flight.";
  const response = await fetch(`${apiUrl.replace(/\/$/, "")}/audit/walkthrough-sync`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question_text_solver: question,
      options: [],
      givens: [],
      requested_quantity: null,
      suggested_engine_case: null,
      diagram: null,
    }),
  });
  if (!response.ok) {
    throw new Error(`Audit API request failed: ${response.status} ${await response.text()}`);
  }
  return response.json();
}

async function importPlaywright() {
  const frontendRequire = createRequire(new URL("../frontend/package.json", import.meta.url));
  try {
    return frontendRequire("playwright");
  } catch (error) {
    throw new Error(
      "Playwright is required for render verification. Install it in the frontend workspace with `npm install -D playwright` and run browser installation if needed.",
      { cause: error },
    );
  }
}

function parseArgs(items) {
  const parsed = {};
  for (let index = 0; index < items.length; index += 1) {
    const item = items[index];
    if (!item.startsWith("--")) continue;
    const key = item.slice(2).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
    const next = items[index + 1];
    if (!next || next.startsWith("--")) {
      parsed[key] = true;
    } else {
      parsed[key] = next;
      index += 1;
    }
  }
  return parsed;
}

function csv(value) {
  return String(value ?? "")
    .split(",")
    .map(item => item.trim())
    .filter(Boolean);
}

async function assertRenderedEntity({ board, stepId, entityId, failures }) {
  const count = await board.locator(`[data-audit-entity=${JSON.stringify(entityId)}]`).count();
  if (count < 1) failures.push(`${stepId}: expected visible entity ${entityId}.`);
}

async function assertTemplateLineExists({ board, stepId, lineId, failures }) {
  const count = await board.locator(`[data-audit-template-line-id=${JSON.stringify(lineId)}]`).count();
  if (count < 1) failures.push(`${stepId}: expected template line ${lineId}.`);
}

async function assertTemplateLineAngle({ board, stepId, lineId, expectedDeg, failures }) {
  const line = board.locator(`[data-audit-template-line-id=${JSON.stringify(lineId)}]`);
  const count = await line.count();
  if (count !== 1) {
    failures.push(`${stepId}: expected one template line ${lineId}, found ${count}.`);
    return;
  }
  const actualDeg = Number(await line.first().getAttribute("data-audit-template-angle-deg"));
  if (!Number.isFinite(actualDeg)) {
    failures.push(`${stepId}: template line ${lineId} has no numeric angle audit attribute.`);
    return;
  }
  const delta = angleDeltaDeg(actualDeg, expectedDeg);
  if (delta > 2.0) {
    failures.push(`${stepId}: template line ${lineId} angle=${actualDeg}deg, expected ${expectedDeg}deg from question theta.`);
  }
}

function signedAngle(degrees) {
  if (!Number.isFinite(degrees)) return 0;
  const normalized = ((degrees % 360) + 360) % 360;
  return normalized > 180 ? normalized - 360 : normalized;
}

function angleDeltaDeg(left, right) {
  return Math.abs(signedAngle(left - right));
}

main().catch(error => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
