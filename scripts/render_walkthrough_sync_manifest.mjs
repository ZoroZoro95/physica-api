#!/usr/bin/env node
/**
 * Batch browser render audit for manifest walkthrough-sync artifacts.
 */

import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { createRequire } from "node:module";

const args = parseArgs(process.argv.slice(2));
const auditDir = path.resolve(args.auditDir ?? "questions/walkthrough_sync_manifest_audits/latest");
const frontendUrl = args.frontend ?? "http://127.0.0.1:3003";

async function main() {
  const payloadPaths = await findPayloads(auditDir);
  if (!payloadPaths.length) {
    throw new Error(`No render_payload.json files found under ${auditDir}`);
  }

  const { chromium } = await importPlaywright();
  const browser = await chromium.launch({ headless: args.headed ? false : true });
  const failures = [];
  const visualIndexEntries = [];
  let checkedBeats = 0;
  try {
    for (const payloadPath of payloadPaths) {
      const caseId = path.basename(path.dirname(payloadPath));
      const payload = JSON.parse(await fs.readFile(payloadPath, "utf8"));
      const result = await checkPayload({ browser, payload, caseId });
      checkedBeats += result.checkedBeats;
      failures.push(...result.failures);
      visualIndexEntries.push(...result.visualIndexEntries);
    }
  } finally {
    await browser.close();
  }

  if (args.visualIndexPath) {
    const indexPath = path.resolve(args.visualIndexPath);
    await fs.mkdir(path.dirname(indexPath), { recursive: true });
    await fs.writeFile(indexPath, JSON.stringify({
      generatedAt: new Date().toISOString(),
      auditDir,
      frontendUrl,
      allBeats: Boolean(args.allBeats),
      checkLayout: Boolean(args.checkLayout),
      checkVariation: Boolean(args.checkVariation),
      totalVisuals: visualIndexEntries.length,
      visuals: visualIndexEntries,
    }, null, 2) + "\n");
  }

  if (failures.length) {
    console.error("Manifest render audit failed:");
    for (const failure of failures) console.error(`- ${failure}`);
    process.exit(1);
  }
  console.log(`Manifest render audit passed: ${payloadPaths.length} cases, ${checkedBeats} ${args.allBeats ? "beats" : "beat probes"} checked.`);
}

async function checkPayload({ browser, payload, caseId }) {
  const beatChecks = beatChecksForPayload(payload, Boolean(args.allBeats));
  const failures = [];
  const visualIndexEntries = [];
  let checkedBeats = 0;
  if (!payload?.animation_scene_spec) {
    return { checkedBeats, failures: [`${caseId}: missing animation_scene_spec.`] };
  }
  if (!beatChecks.length) {
    return { checkedBeats, failures: [`${caseId}: no ${args.allBeats ? "beats" : "render probes"}.`] };
  }

  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const visualSignatures = [];
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
    const fullLifecycleCount = await fullLifecycle.count();
    if (fullLifecycleCount !== 1) {
      failures.push(`${caseId}: full lifecycle 3D audit surface count=${fullLifecycleCount}.`);
    } else {
      const isFull = await fullLifecycle.first().getAttribute("data-audit-full-lifecycle");
      if (isFull !== "true") failures.push(`${caseId}: full lifecycle surface is not marked true.`);
    }

    for (const beat of beatChecks) {
      const probe = beat.render_probe ?? beat.probe ?? beat ?? {};
      if (!args.allBeats && probe.requires_render_verification === false) continue;
      checkedBeats += 1;
      const stepId = String(beat.step_id ?? probe.step_id ?? "");
      if (!stepId) {
        failures.push(`${caseId}: beat/probe is missing step_id.`);
        continue;
      }
      const board = page.locator(`[data-audit-surface='teaching-board-2d'][data-audit-step-id=${JSON.stringify(stepId)}]`);
      const boardCount = await board.count();
      if (boardCount !== 1) {
        failures.push(`${caseId}/${stepId}: expected one teaching board, found ${boardCount}.`);
        continue;
      }
      const templateKind = await board.first().getAttribute("data-audit-template-kind");
      const visualEntry = {
        caseId,
        stepId,
        beatId: String(beat.beat_id ?? beat.id ?? ""),
        title: String(beat.title ?? ""),
        learnerMessage: String(beat.learner_message ?? ""),
        beatVisual: String(beat.beat_visual ?? ""),
        visualAction: visualActionForBeat(payload, beat, stepId),
        templateKind: templateKind || "",
        engineCase: String(payload?.solver?.engine_case ?? payload?.animation_scene_spec?.problem?.engine_case ?? ""),
        answer: String(payload?.solver?.answer ?? ""),
        screenshotHash: "",
        screenshotPath: "",
        svgPath: "",
      };

      const visibleVectorIds = csv(await board.first().getAttribute("data-audit-visible-vector-ids"));
      for (const vectorId of probe.expected_vector_ids ?? []) {
        if (!visibleVectorIds.includes(vectorId)) {
          failures.push(`${caseId}/${stepId}: expected visible vector ${vectorId}, got [${visibleVectorIds.join(", ")}].`);
        }
        const vectorCount = await board.locator(`[data-audit-vector-id=${JSON.stringify(vectorId)}]`).count();
        if (vectorCount < 1) failures.push(`${caseId}/${stepId}: vector element ${vectorId} is not rendered.`);
      }

      for (const pointId of probe.expected_point_ids ?? []) {
        const count = await board.locator(`[data-audit-point-id=${JSON.stringify(pointId)}]`).count();
        if (count < 1) failures.push(`${caseId}/${stepId}: point ${pointId} is not rendered.`);
      }

      for (const surfaceId of probe.expected_surface_ids ?? []) {
        const count = await board.locator(`[data-audit-surface-id=${JSON.stringify(surfaceId)}]`).count();
        if (count < 1) failures.push(`${caseId}/${stepId}: surface ${surfaceId} is not rendered.`);
      }

      const showTrajectory = await board.first().getAttribute("data-audit-show-trajectory");
      if (typeof probe.expected_show_trajectory === "boolean" && probe.expected_show_trajectory !== (showTrajectory === "true")) {
        failures.push(`${caseId}/${stepId}: trajectory visibility expected=${probe.expected_show_trajectory} rendered=${showTrajectory}.`);
      }

      if (args.checkLayout) {
        const layoutFailures = await board.first().evaluate((boardNode, options) => {
          const labelGapPx = Number(options.labelGapPx) || 2;
          const geometryGapPx = Number(options.geometryGapPx) || 5;
          const minOverlapAreaPx = Number(options.minOverlapAreaPx) || 18;
          const failures = [];
          const labels = Array.from(boardNode.querySelectorAll("[data-audit-label-key]"))
            .map(element => ({
              key: element.getAttribute("data-audit-label-key") || "label",
              rect: rectOf(element),
            }))
            .filter(item => item.rect.width > 1 && item.rect.height > 1);

          for (let first = 0; first < labels.length; first += 1) {
            for (let second = first + 1; second < labels.length; second += 1) {
              const overlap = rectOverlapArea(expandRect(labels[first].rect, labelGapPx), expandRect(labels[second].rect, labelGapPx));
              if (overlap > minOverlapAreaPx) {
                failures.push(`label ${labels[first].key} overlaps label ${labels[second].key} (${Math.round(overlap)} px²)`);
              }
            }
          }

          const lines = Array.from(boardNode.querySelectorAll("[data-audit-vector-id] line, [data-audit-surface-id] line, line[data-audit-template-line-id], path[data-audit-template-line-id]"))
            .flatMap(geometrySegmentsFromElement)
            .filter(Boolean);
          for (const label of labels) {
            const expanded = expandRect(label.rect, geometryGapPx);
            for (const line of lines) {
              if (segmentIntersectsRect(line.from, line.to, expanded)) {
                failures.push(`label ${label.key} intersects ${line.kind} ${line.id}`);
              }
            }
          }

          const points = Array.from(boardNode.querySelectorAll("[data-audit-point-id] circle"))
            .map(element => ({
              id: element.closest("[data-audit-point-id]")?.getAttribute("data-audit-point-id") || "point",
              rect: expandRect(rectOf(element), geometryGapPx),
            }))
            .filter(item => item.rect.width > 1 && item.rect.height > 1);
          for (const label of labels) {
            for (const point of points) {
              const overlap = rectOverlapArea(label.rect, point.rect);
              if (overlap > minOverlapAreaPx) failures.push(`label ${label.key} overlaps point ${point.id} (${Math.round(overlap)} px²)`);
            }
          }

          return failures.slice(0, 16);

          function rectOf(element) {
            const rect = element.getBoundingClientRect();
            return {
              left: rect.left,
              right: rect.right,
              top: rect.top,
              bottom: rect.bottom,
              width: rect.width,
              height: rect.height,
            };
          }

          function expandRect(rect, gap) {
            return {
              left: rect.left - gap,
              right: rect.right + gap,
              top: rect.top - gap,
              bottom: rect.bottom + gap,
              width: rect.width + gap * 2,
              height: rect.height + gap * 2,
            };
          }

          function rectOverlapArea(a, b) {
            const width = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
            const height = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
            return width * height;
          }

          function geometrySegmentsFromElement(element) {
            if (element.tagName.toLowerCase() === "path") return pathSegmentsFromElement(element);
            const line = lineFromElement(element);
            return line ? [line] : [];
          }

          function pathSegmentsFromElement(element) {
            const matrix = element.getScreenCTM();
            if (!matrix || typeof element.getTotalLength !== "function" || typeof element.getPointAtLength !== "function") return [];
            const total = element.getTotalLength();
            if (!Number.isFinite(total) || total <= 0) return [];
            const id = element.getAttribute("data-audit-template-line-id") || "path";
            const segments = [];
            const sampleCount = Math.max(6, Math.ceil(total / 8));
            let previous = new DOMPoint(0, 0).matrixTransform(matrix);
            for (let index = 0; index <= sampleCount; index += 1) {
              const point = element.getPointAtLength((total * index) / sampleCount);
              const current = new DOMPoint(point.x, point.y).matrixTransform(matrix);
              if (index > 0) {
                segments.push({
                  from: { x: previous.x, y: previous.y },
                  to: { x: current.x, y: current.y },
                  kind: "template",
                  id,
                });
              }
              previous = current;
            }
            return segments;
          }

          function lineFromElement(element) {
            const matrix = element.getScreenCTM();
            if (!matrix) return null;
            const from = new DOMPoint(Number(element.getAttribute("x1")), Number(element.getAttribute("y1"))).matrixTransform(matrix);
            const to = new DOMPoint(Number(element.getAttribute("x2")), Number(element.getAttribute("y2"))).matrixTransform(matrix);
            const vector = element.closest("[data-audit-vector-id]");
            const surface = element.closest("[data-audit-surface-id]");
            const template = element.getAttribute("data-audit-template-line-id");
            return {
              from: { x: from.x, y: from.y },
              to: { x: to.x, y: to.y },
              kind: vector ? "vector" : surface ? "surface" : "template",
              id: vector?.getAttribute("data-audit-vector-id") || surface?.getAttribute("data-audit-surface-id") || template || "line",
            };
          }

          function segmentIntersectsRect(from, to, rect) {
            if (pointInRect(from, rect) || pointInRect(to, rect)) return true;
            const corners = [
              { x: rect.left, y: rect.top },
              { x: rect.right, y: rect.top },
              { x: rect.right, y: rect.bottom },
              { x: rect.left, y: rect.bottom },
            ];
            for (let index = 0; index < corners.length; index += 1) {
              if (segmentsIntersect(from, to, corners[index], corners[(index + 1) % corners.length])) return true;
            }
            return false;
          }

          function pointInRect(point, rect) {
            return point.x >= rect.left && point.x <= rect.right && point.y >= rect.top && point.y <= rect.bottom;
          }

          function segmentsIntersect(a, b, c, d) {
            const o1 = orientation(a, b, c);
            const o2 = orientation(a, b, d);
            const o3 = orientation(c, d, a);
            const o4 = orientation(c, d, b);
            return o1 * o2 <= 0 && o3 * o4 <= 0 && boxesIntersect(a, b, c, d);
          }

          function orientation(a, b, c) {
            const value = (b.y - a.y) * (c.x - b.x) - (b.x - a.x) * (c.y - b.y);
            if (Math.abs(value) < 0.0001) return 0;
            return value > 0 ? 1 : -1;
          }

          function boxesIntersect(a, b, c, d) {
            return (
              Math.max(Math.min(a.x, b.x), Math.min(c.x, d.x)) <= Math.min(Math.max(a.x, b.x), Math.max(c.x, d.x))
              && Math.max(Math.min(a.y, b.y), Math.min(c.y, d.y)) <= Math.min(Math.max(a.y, b.y), Math.max(c.y, d.y))
            );
          }
        }, {
          labelGapPx: args.labelGapPx ?? 2,
          geometryGapPx: args.geometryGapPx ?? 5,
          minOverlapAreaPx: args.minOverlapAreaPx ?? 18,
        });
        for (const failure of layoutFailures) failures.push(`${caseId}/${stepId}: ${failure}.`);
      }

      if (args.checkVariation || args.screenshotDir) {
        const screenshot = await board.first().screenshot();
        const screenshotHash = crypto.createHash("sha1").update(screenshot).digest("hex");
        visualEntry.screenshotHash = screenshotHash;
        visualSignatures.push({
          stepId,
          visualAction: visualEntry.visualAction,
          templateKind: templateKind || "",
          screenshotHash,
        });
        if (args.screenshotDir) {
          const caseDir = path.join(path.resolve(args.screenshotDir), caseId);
          await fs.mkdir(caseDir, { recursive: true });
          const safeStep = stepId.replace(/[^a-z0-9_-]+/gi, "_").slice(0, 80);
          const screenshotPath = path.join(caseDir, `${safeStep}.png`);
          await fs.writeFile(screenshotPath, screenshot);
          visualEntry.screenshotPath = screenshotPath;
        }
      }

      if (args.svgDir) {
        const svgLocator = board.locator("[data-audit-board-svg='true']").first();
        const svgCount = await svgLocator.count();
        if (svgCount < 1) {
          failures.push(`${caseId}/${stepId}: teaching board SVG element not found.`);
        } else {
          const svgText = await svgLocator.evaluate(svg => {
            if (!svg.getAttribute("xmlns")) svg.setAttribute("xmlns", "http://www.w3.org/2000/svg");
            return svg.outerHTML;
          });
          const caseDir = path.join(path.resolve(args.svgDir), caseId);
          await fs.mkdir(caseDir, { recursive: true });
          const safeStep = stepId.replace(/[^a-z0-9_-]+/gi, "_").slice(0, 80);
          const svgPath = path.join(caseDir, `${safeStep}.svg`);
          await fs.writeFile(svgPath, svgText);
          visualEntry.svgPath = svgPath;
        }
      }

      if (args.visualIndexPath || args.svgDir || args.screenshotDir) {
        visualIndexEntries.push(visualEntry);
      }
    }
    if (args.checkVariation) {
      failures.push(...visualVariationFailures(caseId, visualSignatures));
    }
  } finally {
    await page.close();
  }

  return { checkedBeats, failures, visualIndexEntries };
}

function visualActionForBeat(payload, beat, stepId) {
  const direct = beat?.animation_action ?? beat?.visual_action ?? beat?.render_probe?.animation_action ?? beat?.render_probe?.visual_action;
  if (direct) return String(direct);
  const storyboardStep = (payload?.animation_scene_spec?.storyboard ?? []).find(step => String(step?.step_id ?? "") === stepId);
  return String(storyboardStep?.visual_action ?? "");
}

function visualVariationFailures(caseId, signatures) {
  const relevant = signatures.filter(item => item.stepId && item.visualAction);
  if (relevant.length < 3) return [];
  const actions = uniqueValues(relevant.map(item => item.visualAction));
  if (actions.length < 3) return [];
  const textbook = relevant.filter(item => item.templateKind);
  const failures = [];
  if (textbook.length >= 3) {
    const templates = uniqueValues(textbook.map(item => item.templateKind));
    if (templates.length <= 1) {
      failures.push(`${caseId}: ${actions.length} storyboard actions all render one textbook template (${templates[0] || "unknown"}).`);
    }
  }
  const hashes = uniqueValues(relevant.map(item => item.screenshotHash).filter(Boolean));
  if (hashes.length <= 1) {
    failures.push(`${caseId}: ${actions.length} storyboard actions render identical teaching-board screenshots.`);
  }
  return failures;
}

function uniqueValues(items) {
  return Array.from(new Set(items.filter(Boolean)));
}

function beatChecksForPayload(payload, includeAllBeats) {
  const pairings = payload?.audit?.beat_pairings ?? [];
  if (includeAllBeats) {
    if (pairings.length) return pairings;
    return (payload?.animation_scene_spec?.storyboard ?? []).map(step => ({
      step_id: step.step_id,
      render_probe: {},
    }));
  }
  const pairingProbes = pairings
    .filter(pairing => pairing?.render_probe?.requires_render_verification !== false)
    .map(pairing => ({
      step_id: pairing.step_id ?? pairing.render_probe?.step_id,
      render_probe: pairing.render_probe ?? {},
    }));
  if (pairingProbes.length) return pairingProbes;
  return payload?.audit?.render_probe_contract?.beat_probes ?? [];
}

async function findPayloads(root) {
  const entries = await fs.readdir(root, { withFileTypes: true });
  const payloads = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const payloadPath = path.join(root, entry.name, "render_payload.json");
    try {
      await fs.access(payloadPath);
      payloads.push(payloadPath);
    } catch {
      // Ignore non-case directories.
    }
  }
  return payloads.sort();
}

async function importPlaywright() {
  const frontendRequire = createRequire(new URL("../frontend/package.json", import.meta.url));
  try {
    return frontendRequire("playwright");
  } catch (error) {
    throw new Error("Playwright is required for render verification. Install it in the frontend workspace.", { cause: error });
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

main().catch(error => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
