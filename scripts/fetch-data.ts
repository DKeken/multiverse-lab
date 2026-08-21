#!/usr/bin/env bun
import { dirname, join } from "node:path";
import { mkdir } from "node:fs/promises";

type HttpDataset = {
  id: string; group: string; kind: "http"; url: string; path: string;
  sha256: string; bytes: number;
};
type GitDataset = {
  id: string; group: string; kind: "git"; url: string; path: string;
  revision: string;
};
type ManualDataset = {
  id: string; group: string; kind: "manual"; reason: string;
};
type Dataset = HttpDataset | GitDataset | ManualDataset;

function isDataset(value: unknown): value is Dataset {
  if (!value || typeof value !== "object") return false;
  if (!("id" in value) || typeof value.id !== "string") return false;
  if (!("group" in value) || typeof value.group !== "string") return false;
  if (!("kind" in value) || typeof value.kind !== "string") return false;
  if (value.kind === "manual") return "reason" in value && typeof value.reason === "string";
  if (!("url" in value) || typeof value.url !== "string" || !("path" in value) || typeof value.path !== "string") return false;
  if (value.kind === "git") return "revision" in value && typeof value.revision === "string";
  return value.kind === "http" && "sha256" in value && typeof value.sha256 === "string" && "bytes" in value && typeof value.bytes === "number";
}
const root = join(import.meta.dir, "..");
const rawRegistry: unknown = await Bun.file(join(root, "data/registry.json")).json();
if (!rawRegistry || typeof rawRegistry !== "object" || !("datasets" in rawRegistry) || !Array.isArray(rawRegistry.datasets) || !rawRegistry.datasets.every(isDataset)) {
  throw new Error("data/registry.json does not match dataset registry contract");
}
const datasets: Dataset[] = rawRegistry.datasets;
const groupIndex = process.argv.indexOf("--group");
const group = groupIndex >= 0 ? process.argv[groupIndex + 1] : undefined;
if (!group) throw new Error("Usage: bun scripts/fetch-data.ts --group fixture|wmap");

for (const entry of datasets.filter((item) => item.group === group)) {
  if (entry.kind === "manual") throw new Error(`${entry.id} requires explicit approval: ${entry.reason}`);
  const target = join(root, entry.path);
  await mkdir(dirname(target), { recursive: true });
  if (entry.kind === "http") {
    if (await Bun.file(target).exists()) {
      const existing = new Bun.CryptoHasher("sha256").update(await Bun.file(target).arrayBuffer()).digest("hex");
      if (existing === entry.sha256) { console.log(`verified ${entry.id}`); continue; }
      throw new Error(`${entry.id}: existing file hash mismatch; remove it explicitly before refetching`);
    }
    const response = await fetch(entry.url);
    if (!response.ok) throw new Error(`${entry.id}: HTTP ${response.status}`);
    const bytes = new Uint8Array(await response.arrayBuffer());
    if (bytes.byteLength !== entry.bytes) throw new Error(`${entry.id}: byte-size mismatch`);
    const hash = new Bun.CryptoHasher("sha256").update(bytes).digest("hex");
    if (hash !== entry.sha256) throw new Error(`${entry.id}: SHA-256 mismatch`);
    await Bun.write(target, bytes);
    console.log(`fetched ${entry.id} ${bytes.byteLength} bytes`);
  } else if (entry.kind === "git") {
    if (await Bun.file(join(target, ".git/HEAD")).exists()) {
      const check = Bun.spawnSync(["git", "-C", target, "rev-parse", "HEAD"]);
      if (check.exitCode === 0 && check.stdout.toString().trim() === entry.revision) { console.log(`verified ${entry.id}`); continue; }
      throw new Error(`${entry.id}: existing checkout is not pinned revision`);
    }
    let result = Bun.spawnSync(["git", "clone", "--filter=blob:none", entry.url, target], { stdout: "inherit", stderr: "inherit" });
    if (result.exitCode !== 0) throw new Error(`${entry.id}: clone failed`);
    result = Bun.spawnSync(["git", "-C", target, "checkout", "--detach", entry.revision], { stdout: "inherit", stderr: "inherit" });
    if (result.exitCode !== 0) throw new Error(`${entry.id}: revision checkout failed`);
    console.log(`fetched ${entry.id}@${entry.revision}`);
  }
}
