// Submit a serialized prediction parquet to its EPI-Eval sibling dataset
// as a community pull request via @huggingface/hub.
//
// Sibling-dataset name convention: "EPI-Eval/{target}-predictions". This
// matches the locked-in v2 design from FOLLOW_UPS.md. The repo must
// already exist on HF — bootstrapping new sibling datasets is a
// maintainer step.

import { commit, type RepoDesignation } from "@huggingface/hub";
import { serializePredictionParquet, type SubmissionMetadata } from "./parquet";
import type { UserDataset } from "./types";

export const PREDICTIONS_ORG = "EPI-Eval";

export function siblingRepoId(targetDatasetId: string): string {
  return `${PREDICTIONS_ORG}/${targetDatasetId}-predictions`;
}

export interface SubmitArgs {
  dataset: UserDataset;
  meta: SubmissionMetadata;
  accessToken: string;
}

export interface SubmitResult {
  pullRequestUrl: string;
  rowCount: number;
  filename: string;
  repoId: string;
}

export async function submitPredictionPr(args: SubmitArgs): Promise<SubmitResult> {
  const { dataset, meta, accessToken } = args;
  const serialized = serializePredictionParquet(dataset, meta);

  const repoId = siblingRepoId(meta.targetDataset);
  const repo: RepoDesignation = { type: "dataset", name: repoId };

  const title = truncate(
    `Add ${meta.modelName || "predictions"} from ${meta.submitter}`,
    140
  );
  const body = buildPrBody(meta, serialized.rowCount, serialized.filename);

  const result = await commit({
    repo,
    accessToken,
    title,
    description: body,
    isPullRequest: true,
    operations: [
      {
        operation: "addOrUpdate",
        path: serialized.filename,
        content: new Blob([serialized.buffer], { type: "application/octet-stream" })
      }
    ]
  });

  if (!result?.pullRequestUrl) {
    throw new Error(
      "HuggingFace accepted the commit but did not return a pull request URL. " +
        "Check the dataset page for the PR manually."
    );
  }

  return {
    pullRequestUrl: result.pullRequestUrl,
    rowCount: serialized.rowCount,
    filename: serialized.filename,
    repoId
  };
}

function buildPrBody(meta: SubmissionMetadata, rowCount: number, filename: string): string {
  return [
    `Submitter: ${meta.submitter}`,
    `Model: ${meta.modelName}`,
    `Target: ${meta.targetDataset} / ${meta.targetColumn}`,
    `Rows: ${rowCount}`,
    `File: ${filename}`,
    "",
    meta.description || "_(no description provided)_"
  ].join("\n");
}

function truncate(s: string, max: number): string {
  return s.length <= max ? s : s.slice(0, max - 1) + "…";
}
