import json
import boto3
import uuid
from datetime import datetime

def lambda_handler(event, context):
    # Initialize clients
    comprehend_medical = boto3.client('comprehendmedical', region_name='us-east-1')
    healthlake = boto3.client('healthlake', region_name='us-east-1')
    
    # Get the clinical text
    clinical_text = event.get('text', '')
    patient_id = event.get('patient_id', '')
    datastore_id = event.get('datastore_id', '')
    
    try:
        # Extract medical entities
        entities_response = comprehend_medical.detect_entities_v2(
            Text=clinical_text
        )
        
        # Extract medical relationships
        relationships_response = comprehend_medical.detect_relationships_v2(
            Text=clinical_text
        )
        
        # Extract PHI
        phi_response = comprehend_medical.detect_phi(
            Text=clinical_text
        )
        
        # Process medications and create FHIR MedicationStatement resources
        medications = []
        for entity in entities_response['Entities']:
            if entity['Category'] == 'MEDICATION':
                medication_statement = {
                    "resourceType": "MedicationStatement",
                    "id": str(uuid.uuid4()),
                    "status": "active",
                    "medicationCodeableConcept": {
                        "text": entity['Text']
                    },
                    "subject": {
                        "reference": f"Patient/{patient_id}"
                    },
                    "effectiveDateTime": datetime.now().isoformat() + "Z",
                    "note": [
                        {
                            "text": f"Extracted from clinical note. Confidence: {entity['Score']:.2f}"
                        }
                    ]
                }
                medications.append(medication_statement)
        
        # Process conditions and create FHIR Condition resources
        conditions = []
        for entity in entities_response['Entities']:
            if entity['Category'] == 'MEDICAL_CONDITION':
                condition = {
                    "resourceType": "Condition",
                    "id": str(uuid.uuid4()),
                    "clinicalStatus": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                                "code": "active"
                            }
                        ]
                    },
                    "code": {
                        "text": entity['Text']
                    },
                    "subject": {
                        "reference": f"Patient/{patient_id}"
                    },
                    "recordedDate": datetime.now().isoformat() + "Z",
                    "note": [
                        {
                            "text": f"Extracted from clinical note. Confidence: {entity['Score']:.2f}"
                        }
                    ]
                }
                conditions.append(condition)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Medical NLP processing completed',
                'entities_found': len(entities_response['Entities']),
                'medications': medications,
                'conditions': conditions,
                'phi_detected': len(phi_response['Entities'])
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }