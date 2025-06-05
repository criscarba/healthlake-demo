#!/bin/bash

JOB_ID=$1

aws healthlake describe-fhir-import-job \
    --profile iamadmin-datalake-healthlake-365528423741 \
    --region us-east-1 \
    --datastore-id "$(terraform -chdir=../terraform output -raw healthlake_datastore_id)" \
    --job-id $JOB_ID