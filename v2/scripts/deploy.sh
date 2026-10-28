#!/usr/bin/env bash
# This script has no V1 resource parameters or generic DATABASE_URL fallback.
set +x
set -euo pipefail

test "${GITHUB_REF:-}" = refs/heads/v2
[[ "${GITHUB_SHA:-}" =~ ^[a-f0-9]{40}$ ]]
[[ "${GITHUB_RUN_ID:-}" =~ ^[1-9][0-9]{0,19}$ ]]
[[ "${GITHUB_RUN_ATTEMPT:-}" =~ ^[1-9][0-9]{0,2}$ ]]
: "${V2_GCP_PROJECT_ID:?Set V2_GCP_PROJECT_ID}"
: "${V2_GCP_REGION:?Set V2_GCP_REGION}"
: "${V2_NEON_PROJECT_ID:?Set V2_NEON_PROJECT_ID}"
: "${V2_IMAGE:?Set an immutable V2 image digest}"
[[ "${V2_DATABASE_SECRET_VERSION:-}" =~ ^[1-9][0-9]*$ ]]
[[ "${V2_MIGRATION_SECRET_VERSION:-}" =~ ^[1-9][0-9]*$ ]]
[[ "${V2_SMOKE_SECRET_VERSION:-}" =~ ^[1-9][0-9]*$ ]]
prefix="$V2_GCP_REGION-docker.pkg.dev/$V2_GCP_PROJECT_ID/insurance-claim-v2/server@sha256:"
test "${V2_IMAGE:0:${#prefix}}" = "$prefix"
[[ "${V2_IMAGE#"$prefix"}" =~ ^[a-f0-9]{64}$ ]]

SERVICE=insurance-claim-mcp-v2
JOB=insurance-claim-mcp-v2-migrate
RUNTIME="claim-v2-runtime@$V2_GCP_PROJECT_ID.iam.gserviceaccount.com"
MIGRATOR="claim-v2-migrator@$V2_GCP_PROJECT_ID.iam.gserviceaccount.com"
TAG="candidate-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
SUFFIX="${GITHUB_SHA:0:12}-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
REVISION="$SERVICE-$SUFFIX"
PROBE_WORKSPACE=00000000-0000-4000-8000-000000000001
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
scope=(--project "$V2_GCP_PROJECT_ID" --region "$V2_GCP_REGION")

# Preserve explicit V2 traffic targets, including a latest-revision allocation.
before=$(gcloud run services describe "$SERVICE" "${scope[@]}" --format=json)
prior=$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(",".join("{}={}".format(x["revisionName"],x["percent"]) for x in d["status"].get("traffic",[]) if x.get("percent",0)>0))' <<< "$before")
test -n "$prior"
promoted=false
rollback() {
  result=$?
  if [[ $result != 0 && "$promoted" == true ]]; then
    echo "V2 verification failed; restoring previous V2 traffic" >&2
    gcloud run services update-traffic "$SERVICE" "${scope[@]}" \
      --to-revisions "$prior" --quiet || echo "V2 rollback requires operator attention" >&2
  fi
  exit "$result"
}
trap rollback EXIT

gcloud run jobs deploy "$JOB" "${scope[@]}" --image "$V2_IMAGE" \
  --service-account "$MIGRATOR" --command python --args=-m,claim_mcp_v2.db,migrate \
  --set-env-vars "V2_ENVIRONMENT=production,V2_DATABASE_PROJECT_ID=$V2_NEON_PROJECT_ID,V2_DATABASE_APP_ROLE=insurance_claim_v2_app" \
  --set-secrets "V2_DATABASE_URL=insurance-claim-v2-migration-database-url:$V2_MIGRATION_SECRET_VERSION,V2_SMOKE_KEY=insurance-claim-v2-smoke-key:$V2_SMOKE_SECRET_VERSION" \
  --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 300s --quiet
gcloud run jobs execute "$JOB" "${scope[@]}" --wait --quiet
V2_SMOKE_KEY=$(gcloud secrets versions access "$V2_SMOKE_SECRET_VERSION" \
  --project "$V2_GCP_PROJECT_ID" --secret insurance-claim-v2-smoke-key)
export V2_SMOKE_KEY
test -n "$V2_SMOKE_KEY"

gcloud run deploy "$SERVICE" "${scope[@]}" --image "$V2_IMAGE" \
  --service-account "$RUNTIME" --revision-suffix "$SUFFIX" \
  --port 8080 --memory 512Mi --cpu 1 --min-instances 0 --max-instances 2 \
  --concurrency 40 --timeout 60s --no-traffic --tag "$TAG" \
  --set-env-vars "V2_ENVIRONMENT=production,V2_DATABASE_PROJECT_ID=$V2_NEON_PROJECT_ID,V2_APP_VERSION=$GITHUB_SHA" \
  --set-secrets "V2_DATABASE_URL=insurance-claim-v2-database-url:$V2_DATABASE_SECRET_VERSION" --quiet
after=$(gcloud run services describe "$SERVICE" "${scope[@]}" --format=json)
candidate=$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(next(x["url"] for x in d["status"]["traffic"] if x.get("tag")==sys.argv[1]))' "$TAG" <<< "$after")
python3 "$SCRIPT_DIR/smoke.py" --url "$candidate" --version "$GITHUB_SHA" \
  --key-env V2_SMOKE_KEY --expected-workspace "$PROBE_WORKSPACE"
promoted=true
gcloud run services update-traffic "$SERVICE" "${scope[@]}" --to-revisions "$REVISION=100" --quiet
url=$(gcloud run services describe "$SERVICE" "${scope[@]}" --format='value(status.url)')
python3 "$SCRIPT_DIR/smoke.py" --url "$url" --version "$GITHUB_SHA" \
  --key-env V2_SMOKE_KEY --expected-workspace "$PROBE_WORKSPACE"
echo "V2 release verified. V1 resources were not targeted."
