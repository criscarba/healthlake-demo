import json
import boto3
import os
import logging
from datetime import datetime
from urllib.parse import unquote_plus

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
healthlake_client = boto3.client('healthlake')
s3_client = boto3.client('s3')

def lambda_handler(event, context):
    """
    Lambda function to orchestrate FHIR data import into HealthLake
    Triggered by S3 object creation events
    """
    
    # Get environment variables
    datastore_id = os.environ['HEALTHLAKE_DATASTORE_ID']
    import_role_arn = os.environ['HEALTHLAKE_IMPORT_ROLE_ARN']
    staging_bucket = os.environ['STAGING_BUCKET']
    
    try:
        # Process each S3 event record
        for record in event['Records']:
            # Extract S3 event details
            bucket_name = record['s3']['bucket']['name']
            object_key = unquote_plus(record['s3']['object']['key'])
            
            logger.info(f"Processing file: s3://{bucket_name}/{object_key}")
            
            # Check if it's a FHIR JSON file
            if not object_key.endswith('.json'):
                logger.info(f"Skipping non-JSON file: {object_key}")
                continue
            
            # Read the FHIR resource from S3
            try:
                response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
                fhir_content = response['Body'].read().decode('utf-8')
                fhir_resource = json.loads(fhir_content)
                
                # Validate it's a FHIR resource
                if 'resourceType' not in fhir_resource:
                    logger.error(f"Invalid FHIR resource in {object_key}: missing resourceType")
                    continue
                
                logger.info(f"Found FHIR {fhir_resource['resourceType']} resource")
                
            except Exception as e:
                logger.error(f"Error reading FHIR resource from {object_key}: {str(e)}")
                continue
            
            # Copy file to staging bucket for HealthLake import
            staging_key = f"import-ready/{datetime.now().strftime('%Y/%m/%d')}/{object_key.split('/')[-1]}"
            
            try:
                # Copy to staging bucket
                copy_source = {'Bucket': bucket_name, 'Key': object_key}
                s3_client.copy_object(
                    CopySource=copy_source,
                    Bucket=staging_bucket,
                    Key=staging_key,
                    MetadataDirective='COPY'
                )
                
                logger.info(f"Copied to staging: s3://{staging_bucket}/{staging_key}")
                
                # Create HealthLake import job
                import_job_response = start_healthlake_import(
                    datastore_id,
                    staging_bucket,
                    staging_key,
                    import_role_arn,
                    fhir_resource['resourceType']
                )
                
                logger.info(f"Started HealthLake import job: {import_job_response['JobId']}")
                
                # Store job metadata for tracking
                job_metadata = {
                    'jobId': import_job_response['JobId'],
                    'status': import_job_response['JobStatus'],
                    'submittedAt': datetime.now().isoformat(),  # Use current time instead
                    'sourceFile': f"s3://{bucket_name}/{object_key}",
                    'stagingFile': f"s3://{staging_bucket}/{staging_key}",
                    'resourceType': fhir_resource['resourceType'],
                    'resourceId': fhir_resource.get('id', 'unknown')
                }
                
                # Store job tracking info in S3
                tracking_key = f"import-jobs/{import_job_response['JobId']}.json"
                s3_client.put_object(
                    Bucket=staging_bucket,
                    Key=tracking_key,
                    Body=json.dumps(job_metadata, indent=2),
                    ContentType='application/json'
                )
                
            except Exception as e:
                logger.error(f"Error processing HealthLake import for {object_key}: {str(e)}")
                continue
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully processed {len(event["Records"])} files',
                'timestamp': datetime.now().isoformat()
            })
        }
        
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
        }

def start_healthlake_import(datastore_id, bucket, key, role_arn, resource_type):
    """
    Start a HealthLake import job for a single FHIR resource
    """
    
    job_name = f"import-{resource_type}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    try:
        response = healthlake_client.start_fhir_import_job(
            JobName=job_name,
            InputDataConfig={
                'S3Uri': f"s3://{bucket}/{key}"
            },
            JobOutputDataConfig={
                'S3Configuration': {
                    'S3Uri': f"s3://{bucket}/import-results/",
                    'KmsKeyId': 'alias/aws/s3'  # Use AWS managed S3 key
                }
            },
            DatastoreId=datastore_id,
            DataAccessRoleArn=role_arn,
            ClientToken=f"{job_name}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error starting HealthLake import job: {str(e)}")
        raise

def validate_fhir_resource(resource):
    """
    Basic validation of FHIR resource structure
    """
    required_fields = ['resourceType']
    
    for field in required_fields:
        if field not in resource:
            return False, f"Missing required field: {field}"
    
    # Additional validation for specific resource types
    resource_type = resource.get('resourceType')
    
    if resource_type == 'Patient':
        if 'identifier' not in resource and 'name' not in resource:
            return False, "Patient resource must have either identifier or name"
    
    elif resource_type == 'Observation':
        required_obs_fields = ['status', 'code', 'subject']
        for field in required_obs_fields:
            if field not in resource:
                return False, f"Observation missing required field: {field}"
    
    elif resource_type == 'Procedure':
        required_proc_fields = ['status', 'code', 'subject']
        for field in required_proc_fields:
            if field not in resource:
                return False, f"Procedure missing required field: {field}"
    
    return True, "Valid FHIR resource"

def get_import_job_status(job_id):
    """
    Check the status of a HealthLake import job
    """
    try:
        response = healthlake_client.describe_fhir_import_job(
            DatastoreId=os.environ['HEALTHLAKE_DATASTORE_ID'],
            JobId=job_id
        )
        return response
    except Exception as e:
        logger.error(f"Error getting import job status: {str(e)}")
        return None

def process_batch_import(bucket, prefix):
    """
    Process multiple FHIR files as a batch import
    This function can be called separately for bulk imports
    """
    datastore_id = os.environ['HEALTHLAKE_DATASTORE_ID']
    import_role_arn = os.environ['HEALTHLAKE_IMPORT_ROLE_ARN']
    
    job_name = f"batch-import-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    try:
        response = healthlake_client.start_fhir_import_job(
            JobName=job_name,
            InputDataConfig={
                'S3Uri': f"s3://{bucket}/{prefix}"
            },
            JobOutputDataConfig={
                'S3Configuration': {
                    'S3Uri': f"s3://{bucket}/batch-import-results/",
                    'KmsKeyId': 'alias/aws/s3'  # Use AWS managed S3 key
                }
            },
            DatastoreId=datastore_id,
            DataAccessRoleArn=import_role_arn,
            ClientToken=f"{job_name}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )
        
        logger.info(f"Started batch import job: {response['JobId']}")
        return response
        
    except Exception as e:
        logger.error(f"Error starting batch import job: {str(e)}")
        raise