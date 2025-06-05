#!/bin/bash
# SUPER SIMPLE: Just CURL the HealthLake endpoint for cardiovascular-patient-001

echo "🔍 Getting cardiovascular-patient-001 with CURL..."
echo ""

# The endpoint and patient ID
ENDPOINT="https://healthlake.us-east-1.amazonaws.com/datastore/102cacc56530d43732990d78a3bd751d/r4"
PATIENT_ID="cardiovascular-patient-001"

# Get AWS credentials from your profile
export AWS_PROFILE="iamadmin-datalake-healthlake-365528423741"

echo "📡 Making CURL request to:"
echo "$ENDPOINT/Patient/$PATIENT_ID"
echo ""

 
# Get temporary credentials
TEMP_CREDS=$(aws sts get-session-token --profile iamadmin-datalake-healthlake-365528423741 --region us-east-1 --output json)
ACCESS_KEY=$(echo "$TEMP_CREDS" | jq -r '.Credentials.AccessKeyId')
SECRET_KEY=$(echo "$TEMP_CREDS" | jq -r '.Credentials.SecretAccessKey')
SESSION_TOKEN=$(echo "$TEMP_CREDS" | jq -r '.Credentials.SessionToken')

echo "🔄 Trying with temporary credentials..."

curl -X GET \
"$ENDPOINT/Patient/$PATIENT_ID" \
-H "Accept: application/fhir+json" \
-H "X-Amz-Security-Token: $SESSION_TOKEN" \
--aws-sigv4 "aws:amz:us-east-1:healthlake" \
--user "$ACCESS_KEY:$SECRET_KEY" \
--silent --show-error | jq . || {

echo "❌ CURL with temp credentials failed too"
echo ""
echo "🔍 Raw response (without jq):"
curl -X GET \
    "$ENDPOINT/Patient/$PATIENT_ID" \
    -H "Accept: application/fhir+json" \
    -H "X-Amz-Security-Token: $SESSION_TOKEN" \
    --aws-sigv4 "aws:amz:us-east-1:healthlake" \
    --user "$ACCESS_KEY:$SECRET_KEY" \
    --silent --show-error
}

echo ""
echo "✅ Done!"