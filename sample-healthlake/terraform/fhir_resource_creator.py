import json
import boto3
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import os
import urllib3
import base64
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_fhir_datetime() -> str:
    """
    Get properly formatted FHIR datetime with timezone
    """
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

# Initialize AWS clients
s3_client = boto3.client('s3')
session = boto3.Session()
credentials = session.get_credentials()

def handler(event, context):
    """
    Lambda function to create FHIR resources from NLP processing results
    and store them in AWS HealthLake
    """
    try:
        logger.info("Starting FHIR resource creation from NLP results")
        
        # This function can be triggered by EventBridge or directly
        if 'Records' in event:
            # Triggered by S3 event
            bucket = event['Records'][0]['s3']['bucket']['name']
            key = event['Records'][0]['s3']['object']['key']
            nlp_results = load_nlp_results_from_s3(bucket, key)
        else:
            # Triggered by EventBridge or manual invocation
            # Look for recent NLP results in the output bucket
            nlp_results = get_latest_nlp_results()
        
        if not nlp_results:
            logger.warning("No NLP results found to process")
            return {'statusCode': 200, 'body': 'No results to process'}
        
        # Create FHIR resources
        fhir_resources = create_fhir_resources_from_nlp(nlp_results)
        
        # Store resources in HealthLake
        healthlake_responses = store_resources_in_healthlake(fhir_resources)
        
        # Save processing summary
        save_processing_summary(nlp_results, fhir_resources, healthlake_responses)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'FHIR resources created successfully',
                'resources_created': len(fhir_resources),
                'healthlake_responses': len(healthlake_responses)
            })
        }
        
    except Exception as e:
        logger.error(f"Error creating FHIR resources: {str(e)}")
        raise e

def load_nlp_results_from_s3(bucket: str, key: str) -> Dict[str, Any]:
    """
    Load NLP results from S3
    """
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        nlp_results = json.loads(response['Body'].read().decode('utf-8'))
        logger.info(f"Loaded NLP results from {key}")
        return nlp_results
    except Exception as e:
        logger.error(f"Error loading NLP results: {str(e)}")
        return {}

def get_latest_nlp_results() -> Dict[str, Any]:
    """
    Get the latest NLP results from the output bucket
    """
    try:
        bucket = os.environ['NLP_OUTPUT_BUCKET']
        
        # List recent objects in the processed folder
        response = s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix='processed/',
            MaxKeys=10
        )
        
        if 'Contents' in response:
            # Get the most recent file
            latest_object = max(response['Contents'], key=lambda x: x['LastModified'])
            return load_nlp_results_from_s3(bucket, latest_object['Key'])
        
        return {}
        
    except Exception as e:
        logger.error(f"Error getting latest NLP results: {str(e)}")
        return {}

def create_fhir_resources_from_nlp(nlp_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Create FHIR resources from NLP processing results
    """
    fhir_resources = []
    
    # Step 1: Extract patient info from PHI entities and create Patient resource
    patient_resource = create_patient_from_phi(nlp_results)
    fhir_resources.append(patient_resource)
    
    patient_id = patient_resource['id']
    
    # Step 2: Create DocumentReference for the source text
    document_ref = create_document_reference(nlp_results, patient_id)
    fhir_resources.append(document_ref)
    
    # Step 3: Create medical findings linked to this patient
    observations = create_cardiovascular_observations(nlp_results, patient_id)
    fhir_resources.extend(observations)
    
    medication_statements = create_medication_statements(nlp_results, patient_id)
    fhir_resources.extend(medication_statements)
    
    conditions = create_condition_resources(nlp_results, patient_id)
    fhir_resources.extend(conditions)
    
    logger.info(f"Created {len(fhir_resources)} FHIR resources for patient {patient_id}")
    return fhir_resources

def create_patient_from_phi(nlp_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a Patient resource from PHI entities extracted by Comprehend Medical
    """
    patient_id = str(uuid.uuid4())
    phi_entities = nlp_results.get('phi_entities', [])
    
    # Extract patient information from PHI entities
    patient_info = {
        'names': [],
        'ages': [],
        'ids': [],
        'dates': [],
        'addresses': []
    }
    
    # Process PHI entities to extract patient demographics
    for phi in phi_entities:
        phi_type = phi.get('Type', '').upper()
        phi_text = phi.get('Text', '').strip()
        
        if phi_type == 'NAME' and phi_text:
            patient_info['names'].append(phi_text)
        elif phi_type == 'AGE' and phi_text:
            patient_info['ages'].append(phi_text)
        elif phi_type == 'ID' and phi_text:
            patient_info['ids'].append(phi_text)
        elif phi_type == 'DATE' and phi_text:
            patient_info['dates'].append(phi_text)
        elif phi_type == 'ADDRESS' and phi_text:
            patient_info['addresses'].append(phi_text)
    
    # Build Patient resource
    patient_resource = {
        'resourceType': 'Patient',
        'id': patient_id,
        'meta': {
            'tag': [{
                'system': 'http://gocathlab.com/fhir/tags',
                'code': 'nlp-extracted',
                'display': 'NLP Extracted Patient'
            }]
        },
        'active': True
    }
    
    # Add identifiers if found
    identifiers = []
    for i, patient_id_text in enumerate(patient_info['ids']):
        identifiers.append({
            'use': 'usual',
            'type': {
                'coding': [{
                    'system': 'http://terminology.hl7.org/CodeSystem/v2-0203',
                    'code': 'MR',
                    'display': 'Medical Record Number'
                }]
            },
            'system': 'http://gocathlab.com/patient-id',
            'value': patient_id_text[:50]  # Limit length
        })
    
    if identifiers:
        patient_resource['identifier'] = identifiers
    
    # Add names if found
    names = []
    for name_text in patient_info['names']:
        # Try to parse name (simple approach)
        name_parts = name_text.split()
        if len(name_parts) >= 2:
            names.append({
                'use': 'usual',
                'family': name_parts[-1][:50],  # Last part as family name
                'given': [part[:50] for part in name_parts[:-1]][:3]  # First parts as given names
            })
        else:
            names.append({
                'use': 'usual',
                'text': name_text[:100]
            })
    
    if names:
        patient_resource['name'] = names[:1]  # Use first name found
    else:
        # Fallback name if no PHI name found
        patient_resource['name'] = [{
            'use': 'usual',
            'text': 'Patient from Clinical Note'
        }]
    
    # Add birth date if age found (approximate)
    if patient_info['ages']:
        try:
            age_text = patient_info['ages'][0]
            # Extract numeric age
            age_match = next((char for char in age_text if char.isdigit()), None)
            if age_match:
                age = int(''.join(filter(str.isdigit, age_text)))
                if 0 < age < 150:  # Reasonable age range
                    birth_year = datetime.now().year - age
                    patient_resource['birthDate'] = f"{birth_year}-01-01"
        except:
            pass  # Skip if age parsing fails
    
    # Add addresses if found
    if patient_info['addresses']:
        addresses = []
        for addr_text in patient_info['addresses'][:1]:  # Use first address
            addresses.append({
                'use': 'home',
                'text': addr_text[:200]  # Limit length
            })
        patient_resource['address'] = addresses
    
    # Set gender as unknown since we don't extract it from PHI
    patient_resource['gender'] = 'unknown'
    
    logger.info(f"Created patient from PHI: Names={len(patient_info['names'])}, Ages={len(patient_info['ages'])}, IDs={len(patient_info['ids'])}")
    
    return patient_resource

def create_document_reference(nlp_results: Dict[str, Any], patient_id: str) -> Dict[str, Any]:
    """
    Create a DocumentReference for the source clinical text
    """
    doc_ref_id = str(uuid.uuid4())
    
    # Determine document type based on source
    doc_type = 'clinical-note'
    if 'original_audio_file' in nlp_results:
        doc_type = 'audio-transcription'
    
    # Get the text content
    content_text = nlp_results.get('original_text', nlp_results.get('transcription_text', ''))
    
    return {
        'resourceType': 'DocumentReference',
        'id': doc_ref_id,
        'meta': {
            'tag': [{
                'system': 'http://gocathlab.com/fhir/tags',
                'code': 'nlp-source',
                'display': 'NLP Source Document'
            }]
        },
        'status': 'current',
        'type': {
            'coding': [{
                'system': 'http://loinc.org',
                'code': '11506-3',
                'display': 'Progress note'
            }]
        },
        'subject': {
            'reference': f'Patient/{patient_id}'
        },
        'date': get_fhir_datetime(),
        'content': [{
            'attachment': {
                'contentType': 'text/plain',
                'size': len(content_text.encode('utf-8')),
                'title': 'Clinical Note',
                'data': base64.b64encode(content_text.encode('utf-8')).decode('ascii')
            },
            'format': {
                'system': 'http://ihe.net/fhir/ihe.formatcode.fhir/CodeSystem/formatcode',
                'code': 'urn:ihe:iti:xds:2017:mimeTypeSufficient',
                'display': 'mimeType Sufficient'
            }
        }]
    }

def create_cardiovascular_observations(nlp_results: Dict[str, Any], patient_id: str) -> List[Dict[str, Any]]:
    """
    Create Observation resources for cardiovascular entities
    """
    observations = []
    
    cardio_entities = nlp_results.get('cardiovascular_entities', [])
    
    # Create observations for cardiovascular entities only (limit cath lab for now)
    for entity in cardio_entities[:5]:  # Limit to first 5 to avoid too many resources
        obs_id = str(uuid.uuid4())
        
        observation = {
            'resourceType': 'Observation',
            'id': obs_id,
            'meta': {
                'tag': [{
                    'system': 'http://gocathlab.com/fhir/tags',
                    'code': 'nlp-extracted',
                    'display': 'NLP Extracted'
                }]
            },
            'status': 'final',
            'category': [{
                'coding': [{
                    'system': 'http://terminology.hl7.org/CodeSystem/observation-category',
                    'code': 'survey',
                    'display': 'Survey'
                }]
            }],
            'code': {
                'coding': [{
                    'system': 'http://snomed.info/sct',
                    'code': '404684003',
                    'display': 'Clinical finding'
                }],
                'text': entity.get('text', '')[:50]  # Limit text length
            },
            'subject': {
                'reference': f'Patient/{patient_id}'
            },
            'effectiveDateTime': get_fhir_datetime(),
            'valueString': entity.get('text', '')[:100]  # Limit value length
            # Remove component for now to avoid validation issues
            # 'component': [{
            #     'code': {
            #         'coding': [{
            #             'system': 'http://gocathlab.com/fhir/nlp',
            #             'code': 'confidence-score',
            #             'display': 'NLP Confidence Score'
            #         }]
            #     },
            #     'valueDecimal': round(entity.get('confidence', 0.0), 3)
            # }]
        }
        
        observations.append(observation)
    
    return observations

def create_medication_statements(nlp_results: Dict[str, Any], patient_id: str) -> List[Dict[str, Any]]:
    """
    Create MedicationStatement resources for detected medications
    """
    medication_statements = []
    
    medications = nlp_results.get('medications', [])
    
    for medication in medications[:3]:  # Limit to first 3 medications
        med_statement_id = str(uuid.uuid4())
        
        statement = {
            'resourceType': 'MedicationStatement',
            'id': med_statement_id,
            'meta': {
                'tag': [{
                    'system': 'http://gocathlab.com/fhir/tags',
                    'code': 'nlp-extracted',
                    'display': 'NLP Extracted Medication'
                }]
            },
            'status': 'unknown',
            'medicationCodeableConcept': {
                'text': medication.get('text', '')[:100]  # Limit text length
            },
            'subject': {
                'reference': f'Patient/{patient_id}'
            },
            'effectiveDateTime': get_fhir_datetime()
        }
        
        medication_statements.append(statement)
    
    return medication_statements

def create_procedure_resources(nlp_results: Dict[str, Any], patient_id: str) -> List[Dict[str, Any]]:
    """
    Create Procedure resources for detected procedures
    """
    procedures = []
    
    procedure_entities = nlp_results.get('procedures', [])
    
    for procedure in procedure_entities:
        procedure_id = str(uuid.uuid4())
        
        proc_resource = {
            'resourceType': 'Procedure',
            'id': procedure_id,
            'meta': {
                'tag': [{
                    'system': 'http://gocathlab.com/fhir/tags',
                    'code': 'nlp-extracted',
                    'display': 'NLP Extracted Procedure'
                }]
            },
            'status': 'unknown',
            'code': {
                'coding': [{
                    'system': 'http://snomed.info/sct',
                    'display': procedure.get('text', '')
                }],
                'text': procedure.get('text', '')
            },
            'subject': {
                'reference': f'Patient/{patient_id}'
            },
            'performedDateTime': nlp_results.get('timestamp', datetime.utcnow().isoformat()),
            'note': [{
                'text': f"Extracted from clinical text with confidence: {procedure.get('confidence', 0.0)}"
            }]
        }
        
        procedures.append(proc_resource)
    
    return procedures

def create_condition_resources(nlp_results: Dict[str, Any], patient_id: str) -> List[Dict[str, Any]]:
    """
    Create Condition resources for detected diagnoses
    """
    conditions = []
    
    diagnoses = nlp_results.get('diagnoses', [])
    
    for diagnosis in diagnoses[:3]:  # Limit to first 3 conditions
        condition_id = str(uuid.uuid4())
        
        condition = {
            'resourceType': 'Condition',
            'id': condition_id,
            'meta': {
                'tag': [{
                    'system': 'http://gocathlab.com/fhir/tags',
                    'code': 'nlp-extracted',
                    'display': 'NLP Extracted Condition'
                }]
            },
            'clinicalStatus': {
                'coding': [{
                    'system': 'http://terminology.hl7.org/CodeSystem/condition-clinical',
                    'code': 'active',
                    'display': 'Active'
                }]
            },
            'verificationStatus': {
                'coding': [{
                    'system': 'http://terminology.hl7.org/CodeSystem/condition-ver-status',
                    'code': 'unconfirmed',
                    'display': 'Unconfirmed'
                }]
            },
            'code': {
                'text': diagnosis.get('text', '')[:100]  # Limit text length
            },
            'subject': {
                'reference': f'Patient/{patient_id}'
            },
            'recordedDate': get_fhir_datetime()
        }
        
        conditions.append(condition)
    
    return conditions

def store_resources_in_healthlake(fhir_resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Store FHIR resources in AWS HealthLake using the FHIR API
    """
    healthlake_endpoint = os.environ['HEALTHLAKE_ENDPOINT']
    datastore_id = os.environ['DATASTORE_ID']
    
    responses = []
    http = urllib3.PoolManager()
    
    # Remove '/datastore/{id}' from endpoint if present and add it back
    base_endpoint = healthlake_endpoint.split('/datastore/')[0] if '/datastore/' in healthlake_endpoint else healthlake_endpoint
    fhir_base_url = f"{base_endpoint}/datastore/{datastore_id}/r4"
    
    logger.info(f"Using FHIR base URL: {fhir_base_url}")
    
    for resource in fhir_resources:
        try:
            resource_type = resource['resourceType']
            resource_id = resource['id']
            
            # Create the FHIR resource using PUT (create with specific ID)
            url = f"{fhir_base_url}/{resource_type}/{resource_id}"
            
            # Prepare the request
            body = json.dumps(resource).encode('utf-8')
            
            # Create AWS request for signing
            request = AWSRequest(
                method='PUT',
                url=url,
                data=body,
                headers={
                    'Content-Type': 'application/fhir+json',
                    'Accept': 'application/fhir+json'
                }
            )
            
            # Sign the request with AWS credentials
            SigV4Auth(credentials, 'healthlake', session.region_name).add_auth(request)
            
            # Make the HTTP request
            response = http.request(
                method='PUT',
                url=url,
                body=body,
                headers=dict(request.headers)
            )
            
            logger.info(f"HealthLake response for {resource_type}/{resource_id}: Status {response.status}")
            
            if response.status in [200, 201]:
                # Successfully created/updated
                response_data = {
                    'resourceType': resource_type,
                    'id': resource_id,
                    'status': 'created',
                    'httpStatus': response.status,
                    'location': url
                }
                
                # Try to parse response body
                try:
                    response_body = json.loads(response.data.decode('utf-8'))
                    response_data['fhir_response'] = response_body
                except:
                    response_data['raw_response'] = response.data.decode('utf-8')
                    
            else:
                # Error occurred
                error_body = response.data.decode('utf-8') if response.data else 'Unknown error'
                logger.error(f"HealthLake validation error for {resource_type}/{resource_id}: {error_body}")
                
                response_data = {
                    'resourceType': resource_type,
                    'id': resource_id,
                    'status': 'error',
                    'httpStatus': response.status,
                    'error': error_body
                }
            
            responses.append(response_data)
            logger.info(f"Stored {resource_type} with ID {resource_id}: {response_data['status']}")
            
        except Exception as e:
            logger.error(f"Error storing {resource.get('resourceType', 'Unknown')} resource: {str(e)}")
            responses.append({
                'resourceType': resource.get('resourceType', 'Unknown'),
                'id': resource.get('id', 'Unknown'),
                'status': 'error',
                'error': str(e)
            })
    
    return responses

def save_processing_summary(nlp_results: Dict[str, Any], fhir_resources: List[Dict[str, Any]], healthlake_responses: List[Dict[str, Any]]) -> None:
    """
    Save a summary of the FHIR processing results
    """
    try:
        summary = {
            'timestamp': datetime.utcnow().isoformat(),
            'processing_id': str(uuid.uuid4()),
            'source_file': nlp_results.get('original_text', nlp_results.get('original_audio_file', 'unknown')),
            'nlp_entities_processed': len(nlp_results.get('entities', [])),
            'fhir_resources_created': len(fhir_resources),
            'healthlake_responses': len(healthlake_responses),
            'resource_breakdown': {
                resource_type: len([r for r in fhir_resources if r['resourceType'] == resource_type])
                for resource_type in set(r['resourceType'] for r in fhir_resources)
            },
            'successful_stores': len([r for r in healthlake_responses if r.get('status') == 'created']),
            'failed_stores': len([r for r in healthlake_responses if r.get('status') == 'error'])
        }
        
        output_bucket = os.environ['NLP_OUTPUT_BUCKET']
        summary_key = f"fhir-processing/summary_{summary['processing_id']}.json"
        
        s3_client.put_object(
            Bucket=output_bucket,
            Key=summary_key,
            Body=json.dumps(summary, indent=2),
            ContentType='application/json'
        )
        
        logger.info(f"Processing summary saved to: {summary_key}")
        
    except Exception as e:
        logger.error(f"Error saving processing summary: {str(e)}")
        # Don't raise exception here as it's not critical to the main process