### List data stores
aws healthlake list-fhir-datastores \
    --profile iamadmin-datalake-healthlake-365528423741 \
    --region us-east-1

### Get Data Store Endpoint
aws healthlake describe-fhir-datastore \
    --datastore-id 83a18c9ab49b1d93c9d256f4232b2805 \
    --query 'DatastoreProperties.DatastoreEndpoint' \
    --profile iamadmin-datalake-healthlake-365528423741 \
    --region us-east-1


# Create patient via FHIR API
curl -X POST "https://healthlake.us-east-1.amazonaws.com/datastore/83a18c9ab49b1d93c9d256f4232b2805/r4/Patient" \
    -H "Authorization: AWS4-HMAC-SHA256 Credential=..." \
    -H "Content-Type: application/fhir+json" \
    -d @sample-patient.json


awscurl --service healthlake \
    --profile iamadmin-datalake-healthlake-365528423741 \
    --region us-east-1 \
    -X POST "https://healthlake.us-east-1.amazonaws.com/datastore/83a18c9ab49b1d93c9d256f4232b2805/r4/Patient" \
    -H "Content-Type: application/fhir+json" \
    -d @sample-patient.json    