#!/usr/bin/env bash
# Explicit operator bootstrap; never run automatically in a release or against V1 resources.
set -euo pipefail
: "${V2_GCP_PROJECT_ID:?Set the target project explicitly}"
: "${V2_GCP_REGION:?Set the V2 Cloud Run region}"
REPOSITORY=seothief/insurance-claim-mcp
SERVICE=insurance-claim-mcp-v2
JOB=insurance-claim-mcp-v2-migrate
GAR=insurance-claim-v2
scope=(--project "$V2_GCP_PROJECT_ID")

gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com \
  iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com "${scope[@]}" --quiet
gcloud artifacts repositories describe "$GAR" --location "$V2_GCP_REGION" "${scope[@]}" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "$GAR" --repository-format docker \
    --location "$V2_GCP_REGION" "${scope[@]}" --quiet
for name in claim-v2-runtime claim-v2-migrator claim-v2-deployer; do
  email="$name@$V2_GCP_PROJECT_ID.iam.gserviceaccount.com"
  gcloud iam service-accounts describe "$email" "${scope[@]}" >/dev/null 2>&1 || \
    gcloud iam service-accounts create "$name" "${scope[@]}" --quiet
done
runtime="claim-v2-runtime@$V2_GCP_PROJECT_ID.iam.gserviceaccount.com"
migrator="claim-v2-migrator@$V2_GCP_PROJECT_ID.iam.gserviceaccount.com"
deployer="claim-v2-deployer@$V2_GCP_PROJECT_ID.iam.gserviceaccount.com"
for secret in insurance-claim-v2-database-url insurance-claim-v2-migration-database-url \
  insurance-claim-v2-smoke-key; do
  gcloud secrets describe "$secret" "${scope[@]}" >/dev/null 2>&1 || \
    gcloud secrets create "$secret" --replication-policy automatic "${scope[@]}" --quiet
done
gcloud secrets add-iam-policy-binding insurance-claim-v2-database-url "${scope[@]}" \
  --member "serviceAccount:$runtime" --role roles/secretmanager.secretAccessor --quiet >/dev/null
gcloud secrets add-iam-policy-binding insurance-claim-v2-migration-database-url "${scope[@]}" \
  --member "serviceAccount:$migrator" --role roles/secretmanager.secretAccessor --quiet >/dev/null
for account in "$migrator" "$deployer"; do
  gcloud secrets add-iam-policy-binding insurance-claim-v2-smoke-key "${scope[@]}" \
    --member "serviceAccount:$account" --role roles/secretmanager.secretAccessor --quiet >/dev/null
done
gcloud artifacts repositories add-iam-policy-binding "$GAR" --location "$V2_GCP_REGION" \
  "${scope[@]}" --member "serviceAccount:$deployer" --role roles/artifactregistry.writer --quiet >/dev/null
for account in "$runtime" "$migrator"; do
  gcloud iam service-accounts add-iam-policy-binding "$account" "${scope[@]}" \
    --member "serviceAccount:$deployer" --role roles/iam.serviceAccountUser --quiet >/dev/null
done

# Precreate only V2 resources so the release identity needs no project-wide Cloud Run role.
# Placeholders contain no secrets or business code; they are not a completed V2 deployment.
if ! gcloud run services describe "$SERVICE" --region "$V2_GCP_REGION" "${scope[@]}" >/dev/null 2>&1; then
  gcloud run deploy "$SERVICE" --region "$V2_GCP_REGION" "${scope[@]}" \
    --image us-docker.pkg.dev/cloudrun/container/hello --service-account "$runtime" \
    --max-instances 1 --allow-unauthenticated --quiet
fi
if ! gcloud run jobs describe "$JOB" --region "$V2_GCP_REGION" "${scope[@]}" >/dev/null 2>&1; then
  gcloud run jobs create "$JOB" --region "$V2_GCP_REGION" "${scope[@]}" \
    --image python:3.12-slim --service-account "$migrator" \
    --command python --args=-c,pass --tasks 1 --max-retries 0 --quiet
fi
gcloud run services add-iam-policy-binding "$SERVICE" --region "$V2_GCP_REGION" "${scope[@]}" \
  --member "serviceAccount:$deployer" --role roles/run.developer --quiet >/dev/null
gcloud run jobs add-iam-policy-binding "$JOB" --region "$V2_GCP_REGION" "${scope[@]}" \
  --member "serviceAccount:$deployer" --role roles/run.developer --quiet >/dev/null
gcloud run jobs add-iam-policy-binding "$JOB" --region "$V2_GCP_REGION" "${scope[@]}" \
  --member "serviceAccount:$deployer" --role roles/run.jobsExecutor --quiet >/dev/null

POOL=insurance-claim-v2
PROVIDER=github-v2
gcloud iam workload-identity-pools describe "$POOL" --location global "${scope[@]}" >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools create "$POOL" --location global "${scope[@]}" --quiet
condition="assertion.repository=='$REPOSITORY' && assertion.ref=='refs/heads/v2' && assertion.sub=='repo:$REPOSITORY:environment:v2-production'"
if ! gcloud iam workload-identity-pools providers describe "$PROVIDER" \
  --workload-identity-pool "$POOL" --location global "${scope[@]}" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" \
    --workload-identity-pool "$POOL" --location global "${scope[@]}" \
    --issuer-uri https://token.actions.githubusercontent.com \
    --attribute-mapping 'google.subject=assertion.sub,attribute.repository=assertion.repository' \
    --attribute-condition "$condition" --quiet
else
  # Correct drift on this V2-only provider; never touch the V1 identity pool/provider.
  gcloud iam workload-identity-pools providers update-oidc "$PROVIDER" \
    --workload-identity-pool "$POOL" --location global "${scope[@]}" \
    --attribute-condition "$condition" --quiet
fi
number=$(gcloud projects describe "$V2_GCP_PROJECT_ID" --format='value(projectNumber)')
gcloud iam service-accounts add-iam-policy-binding "$deployer" "${scope[@]}" \
  --member "principalSet://iam.googleapis.com/projects/$number/locations/global/workloadIdentityPools/$POOL/attribute.repository/$REPOSITORY" \
  --role roles/iam.workloadIdentityUser --quiet >/dev/null
echo "V2 GCP scaffolding prepared; database provisioning and verified application release still required."
echo "V2_GCP_SERVICE_ACCOUNT=$deployer"
echo "V2_GCP_WORKLOAD_IDENTITY_PROVIDER=projects/$number/locations/global/workloadIdentityPools/$POOL/providers/$PROVIDER"
