import json
import boto3
import urllib.parse
import logging
from typing import Dict, List, Any
import uuid
from datetime import datetime
import os

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
comprehend_medical = boto3.client('comprehendmedical')
s3_client = boto3.client('s3')

def handler(event, context):
    """
    Lambda function to process clinical notes using Amazon Comprehend Medical
    Triggered by S3 object creation events
    """
    try:
        # Parse S3 event
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'])
        
        logger.info(f"Processing file: {key} from bucket: {bucket}")
        
        # Read the clinical note from S3
        response = s3_client.get_object(Bucket=bucket, Key=key)
        clinical_text = response['Body'].read().decode('utf-8')
        
        # Process with Comprehend Medical
        nlp_results = process_clinical_text(clinical_text)
        
        # Save results to output bucket
        output_bucket = os.environ['NLP_OUTPUT_BUCKET']
        output_key = f"processed/{key.replace('.txt', '_processed.json')}"
        
        s3_client.put_object(
            Bucket=output_bucket,
            Key=output_key,
            Body=json.dumps(nlp_results, indent=2),
            ContentType='application/json'
        )
        
        logger.info(f"NLP processing complete. Results saved to: {output_key}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'NLP processing completed successfully',
                'input_file': key,
                'output_file': output_key,
                'entities_detected': len(nlp_results.get('entities', []))
            })
        }
        
    except Exception as e:
        logger.error(f"Error processing clinical note: {str(e)}")
        raise e

def process_clinical_text(text: str) -> Dict[str, Any]:
    """
    Process clinical text using Amazon Comprehend Medical
    Extract entities relevant to cardiovascular care
    """
    results = {
        'timestamp': datetime.utcnow().isoformat(),
        'processing_id': str(uuid.uuid4()),
        'original_text': text,
        'entities': [],
        'phi_entities': [],
        'medications': [],
        'procedures': [],
        'diagnoses': [],
        'cardiovascular_entities': []
    }
    
    try:
        # Detect medical entities
        entity_response = comprehend_medical.detect_entities_v2(Text=text)
        results['entities'] = entity_response.get('Entities', [])
        
        # Detect PHI
        phi_response = comprehend_medical.detect_phi(Text=text)
        results['phi_entities'] = phi_response.get('Entities', [])
        
        # Process and categorize entities
        categorize_entities(results)
        
        # Extract cardiovascular-specific information
        extract_cardiovascular_entities(results)
        
        logger.info(f"Processed {len(results['entities'])} entities")
        
    except Exception as e:
        logger.error(f"Error in Comprehend Medical processing: {str(e)}")
        results['error'] = str(e)
    
    return results

def categorize_entities(results: Dict[str, Any]) -> None:
    """
    Categorize entities into medications, procedures, and diagnoses
    """
    for entity in results['entities']:
        category = entity.get('Category', '').upper()
        entity_type = entity.get('Type', '').upper()
        text = entity.get('Text', '').lower()
        
        if category == 'MEDICATION':
            results['medications'].append({
                'text': entity.get('Text'),
                'confidence': entity.get('Score'),
                'type': entity_type,
                'attributes': entity.get('Attributes', [])
            })
        
        elif category == 'MEDICAL_CONDITION':
            results['diagnoses'].append({
                'text': entity.get('Text'),
                'confidence': entity.get('Score'),
                'type': entity_type,
                'attributes': entity.get('Attributes', [])
            })
        
        elif category == 'PROCEDURE':
            results['procedures'].append({
                'text': entity.get('Text'),
                'confidence': entity.get('Score'),
                'type': entity_type,
                'attributes': entity.get('Attributes', [])
            })

def extract_cardiovascular_entities(results: Dict[str, Any]) -> None:
    """
    Extract and flag cardiovascular-specific entities
    """
    # Cardiovascular-related terms
    cardio_medications = [
        'statin', 'atorvastatin', 'simvastatin', 'rosuvastatin',
        'beta-blocker', 'metoprolol', 'carvedilol', 'atenolol',
        'ace inhibitor', 'lisinopril', 'enalapril', 'captopril',
        'arb', 'losartan', 'valsartan', 'telmisartan',
        'calcium channel blocker', 'amlodipine', 'diltiazem',
        'diuretic', 'furosemide', 'hydrochlorothiazide',
        'anticoagulant', 'warfarin', 'apixaban', 'rivaroxaban',
        'antiplatelet', 'aspirin', 'clopidogrel', 'prasugrel'
    ]
    
    cardio_procedures = [
        'angioplasty', 'stent', 'stenting', 'catheterization',
        'cardiac catheterization', 'cath lab', 'pci',
        'percutaneous coronary intervention', 'cabg',
        'coronary artery bypass', 'valve replacement',
        'angiogram', 'coronary angiography', 'echocardiogram',
        'stress test', 'ekg', 'electrocardiogram',
        'holter monitor', 'cardiac mri', 'ct angiography'
    ]
    
    cardio_conditions = [
        'coronary artery disease', 'cad', 'myocardial infarction',
        'heart attack', 'angina', 'chest pain', 'arrhythmia',
        'atrial fibrillation', 'heart failure', 'chf',
        'hypertension', 'high blood pressure', 'hyperlipidemia',
        'high cholesterol', 'atherosclerosis', 'stenosis',
        'valve disease', 'cardiomyopathy', 'pericarditis',
        'endocarditis', 'aortic stenosis', 'mitral regurgitation'
    ]
    
    # Check all entities for cardiovascular relevance
    for entity in results['entities']:
        entity_text = entity.get('Text', '').lower()
        category = entity.get('Category', '').upper()
        
        is_cardio = False
        cardio_type = None
        
        if any(term in entity_text for term in cardio_medications):
            is_cardio = True
            cardio_type = 'cardiovascular_medication'
        elif any(term in entity_text for term in cardio_procedures):
            is_cardio = True
            cardio_type = 'cardiovascular_procedure'
        elif any(term in entity_text for term in cardio_conditions):
            is_cardio = True
            cardio_type = 'cardiovascular_condition'
        
        if is_cardio:
            results['cardiovascular_entities'].append({
                'text': entity.get('Text'),
                'confidence': entity.get('Score'),
                'category': category,
                'cardiovascular_type': cardio_type,
                'begin_offset': entity.get('BeginOffset'),
                'end_offset': entity.get('EndOffset'),
                'attributes': entity.get('Attributes', [])
            })