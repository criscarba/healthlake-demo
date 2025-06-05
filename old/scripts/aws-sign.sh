#!/bin/bash

# AWS Signature Version 4 for curl
# Usage: ./aws-sign.sh METHOD URL [DATA_FILE]

METHOD=${1:-GET}
URL=$2
DATA_FILE=$3
PROFILE="iamadmin-datalake-healthlake-365528423741"

# Get AWS credentials
ACCESS_KEY=$(aws configure get aws_access_key_id --profile $PROFILE)
SECRET_KEY=$(aws configure get aws_secret_access_key --profile $PROFILE)
SESSION_TOKEN=$(aws configure get aws_session_token --profile $PROFILE)

# Extract components from URL
if [[ $URL =~ https://([^/]+)(.*) ]]; then
    HOST="${BASH_REMATCH[1]}"
    URI="${BASH_REMATCH[2]}"
else
    echo "Invalid URL format"
    exit 1
fi

# Set up variables
SERVICE="healthlake"
REGION="us-east-1"
DATE=$(date -u +%Y%m%dT%H%M%SZ)
DATESTAMP=$(date -u +%Y%m%d)

# Read payload
if [ -n "$DATA_FILE" ]; then
    PAYLOAD=$(cat "$DATA_FILE")
else
    PAYLOAD=""
fi

# Create canonical request
CONTENT_TYPE="application/fhir+json"
CANONICAL_HEADERS="content-type:${CONTENT_TYPE}\nhost:${HOST}\nx-amz-date:${DATE}"
if [ -n "$SESSION_TOKEN" ]; then
    CANONICAL_HEADERS="${CANONICAL_HEADERS}\nx-amz-security-token:${SESSION_TOKEN}"
    SIGNED_HEADERS="content-type;host;x-amz-date;x-amz-security-token"
else
    SIGNED_HEADERS="content-type;host;x-amz-date"
fi

PAYLOAD_HASH=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hex | sed 's/^.* //')

CANONICAL_REQUEST="${METHOD}\n${URI}\n\n${CANONICAL_HEADERS}\n\n${SIGNED_HEADERS}\n${PAYLOAD_HASH}"

# Create string to sign
ALGORITHM="AWS4-HMAC-SHA256"
CREDENTIAL_SCOPE="${DATESTAMP}/${REGION}/${SERVICE}/aws4_request"
STRING_TO_SIGN="${ALGORITHM}\n${DATE}\n${CREDENTIAL_SCOPE}\n$(echo -en "$CANONICAL_REQUEST" | openssl dgst -sha256 -hex | sed 's/^.* //')"

# Calculate signature
SIGNING_KEY=$(echo -n "aws4_request" | openssl dgst -sha256 -mac HMAC -macopt key:$(echo -n "$SERVICE" | openssl dgst -sha256 -mac HMAC -macopt key:$(echo -n "$REGION" | openssl dgst -sha256 -mac HMAC -macopt key:$(echo -n "$DATESTAMP" | openssl dgst -sha256 -mac HMAC -macopt key:"AWS4$SECRET_KEY" -binary) -binary) -binary) -binary)
SIGNATURE=$(echo -en "$STRING_TO_SIGN" | openssl dgst -sha256 -mac HMAC -macopt key:"$SIGNING_KEY" -hex | sed 's/^.* //')

# Build authorization header
AUTHORIZATION="${ALGORITHM} Credential=${ACCESS_KEY}/${CREDENTIAL_SCOPE}, SignedHeaders=${SIGNED_HEADERS}, Signature=${SIGNATURE}"

# Execute curl command
echo "Executing curl command..."
if [ -n "$SESSION_TOKEN" ]; then
    curl -X "$METHOD" "$URL" \
        -H "Authorization: $AUTHORIZATION" \
        -H "Content-Type: $CONTENT_TYPE" \
        -H "X-Amz-Date: $DATE" \
        -H "X-Amz-Security-Token: $SESSION_TOKEN" \
        -d "$PAYLOAD"
else
    curl -X "$METHOD" "$URL" \
        -H "Authorization: $AUTHORIZATION" \
        -H "Content-Type: $CONTENT_TYPE" \
        -H "X-Amz-Date: $DATE" \
        -d "$PAYLOAD"
fi