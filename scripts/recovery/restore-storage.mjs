#!/usr/bin/env node

import { createClient } from "@supabase/supabase-js";
import { createHash } from "node:crypto";
import { readFile, readdir } from "node:fs/promises";
import { basename, join, relative, resolve, sep } from "node:path";
import process from "node:process";

function fail(message) {
  console.error(`storage restore failed: ${message}`);
  process.exit(1);
}

function requireEnv(name) {
  const value = process.env[name];
  if (!value) fail(`required environment variable is not set: ${name}`);
  return value;
}

async function filesUnder(root) {
  const files = [];
  async function visit(directory) {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const path = join(directory, entry.name);
      if (entry.isDirectory()) await visit(path);
      else if (entry.isFile()) files.push(path);
    }
  }
  await visit(root);
  return files.sort();
}

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

async function loadExpectedHashes(bundle) {
  const lines = (await readFile(join(bundle, "private-file-hashes.jsonl"), "utf8"))
    .split("\n")
    .filter(Boolean);
  const expected = new Map();
  for (const line of lines) {
    const record = JSON.parse(line);
    if (typeof record.path !== "string" || typeof record.sha256 !== "string") {
      fail("private hash manifest contains an invalid record");
    }
    if (record.path.startsWith("storage/")) expected.set(record.path, record.sha256);
  }
  return expected;
}

async function loadObjectMetadata(path) {
  const lines = (await readFile(path, "utf8")).split("\n").filter(Boolean);
  const metadata = new Map();
  for (const line of lines) {
    const record = JSON.parse(line);
    if (typeof record.bucket !== "string" || typeof record.name !== "string") {
      fail("target Storage metadata export contains an invalid record");
    }
    metadata.set(`${record.bucket}\n${record.name}`, record);
  }
  return metadata;
}

const bundleArgument = process.argv[2];
if (!bundleArgument) fail("usage: restore-storage.mjs <completed-backup-directory>");

const bundle = resolve(bundleArgument);
const storageRoot = join(bundle, "storage");
const targetUrl = requireEnv("RECOVERY_TARGET_SUPABASE_URL");
const serviceRoleKey = requireEnv("RECOVERY_TARGET_SERVICE_ROLE_KEY");
const metadataPath = requireEnv("RECOVERY_TARGET_STORAGE_METADATA_JSONL");

const client = createClient(targetUrl, serviceRoleKey, {
  auth: { persistSession: false, autoRefreshToken: false },
});
const expectedHashes = await loadExpectedHashes(bundle);
const objectMetadata = await loadObjectMetadata(metadataPath);
const buckets = (await readdir(storageRoot, { withFileTypes: true }))
  .filter((entry) => entry.isDirectory())
  .map((entry) => entry.name)
  .sort();

const { data: targetBuckets, error: bucketError } = await client.storage.listBuckets();
if (bucketError) fail("target bucket inventory could not be read");
const targetBucketNames = new Set((targetBuckets ?? []).map((bucket) => bucket.name));
for (const bucket of buckets) {
  if (!targetBucketNames.has(bucket)) fail("a backed-up bucket is missing from the target");
}

let uploadedObjects = 0;
let uploadedBytes = 0;
for (const bucket of buckets) {
  const bucketRoot = join(storageRoot, bucket);
  for (const filePath of await filesUnder(bucketRoot)) {
    const objectName = relative(bucketRoot, filePath).split(sep).join("/");
    const manifestPath = `storage/${bucket}/${objectName}`;
    const expectedHash = expectedHashes.get(manifestPath);
    if (!expectedHash) fail("a Storage backup file is missing from the private hash manifest");

    const bytes = await readFile(filePath);
    if (sha256(bytes) !== expectedHash) fail("a Storage backup file failed pre-upload integrity verification");

    const metadata = objectMetadata.get(`${bucket}\n${objectName}`) ?? {};
    const options = { upsert: true };
    if (typeof metadata.contentType === "string" && metadata.contentType) {
      options.contentType = metadata.contentType;
    }
    if (typeof metadata.cacheControl === "string" && metadata.cacheControl) {
      options.cacheControl = metadata.cacheControl;
    }

    const { error: uploadError } = await client.storage.from(bucket).upload(objectName, bytes, options);
    if (uploadError) fail("Storage API upload failed");

    const { data: downloaded, error: downloadError } = await client.storage.from(bucket).download(objectName);
    if (downloadError || !downloaded) fail("restored Storage object could not be read back");
    const downloadedBytes = Buffer.from(await downloaded.arrayBuffer());
    if (sha256(downloadedBytes) !== expectedHash) fail("restored Storage object failed post-upload integrity verification");

    uploadedObjects += 1;
    uploadedBytes += bytes.length;
  }
}

if (uploadedObjects !== expectedHashes.size) {
  fail("restored Storage object count does not match the private hash manifest");
}

// Prove private signed-read behavior without printing an object name or URL.
const artifactFiles = expectedHashes.keys().filter((path) => path.startsWith("storage/artifacts/"));
const firstArtifact = artifactFiles.next();
if (!firstArtifact.done) {
  const objectName = firstArtifact.value.slice("storage/artifacts/".length);
  const { data: signed, error: signError } = await client.storage
    .from("artifacts")
    .createSignedUrl(objectName, 60);
  if (signError || !signed?.signedUrl) fail("private artifact signing failed");
  const response = await fetch(signed.signedUrl);
  if (!response.ok) fail("private signed artifact read failed");
  const signedBytes = Buffer.from(await response.arrayBuffer());
  if (sha256(signedBytes) !== expectedHashes.get(firstArtifact.value)) {
    fail("private signed artifact bytes failed integrity verification");
  }
}

console.log(
  JSON.stringify({
    restored_storage_objects: uploadedObjects,
    restored_storage_bytes: uploadedBytes,
    private_signed_read_verified: !firstArtifact.done,
  }),
);
