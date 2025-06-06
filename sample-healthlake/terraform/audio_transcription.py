import json
import boto3
import urllib.parse
import logging
import uuid
import time
from datetime import datetime
from typing import Dict, Any, Optional
import os

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
transcribe_client = boto3.client('transcribe')
s3_client = boto3.client('s3')
comprehend_medical = boto3.client('comprehendmedical')

def handler(event, context):
    """
    Lambda function to transcribe medical audio files using Amazon Transcribe Medical
    and then process the transcription with Comprehend Medical
    """
    try:
        # Parse S3 event
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'])
        
        logger.info(f"Processing audio file: {key} from bucket: {bucket}")
        
        # Start medical transcription job
        job_name = start_medical_transcription(bucket, key)
        
        # Wait for transcription to complete and get results
        transcription_text = wait_for_transcription_completion(job_name)
        
        if transcription_text:
            # Process transcription with Comprehend Medical
            nlp_results = process_transcription_with_nlp(transcription_text, key)
            
            # Save results to output bucket
            save_transcription_results(nlp_results, key)
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Audio transcription and NLP processing completed',
                    'job_name': job_name,
                    'input_file': key,
                    'transcription_length': len(transcription_text),
                    'entities_detected': len(nlp_results.get('entities', []))
                })
            }
        else:
            raise Exception("Transcription failed or returned empty results")
            
    except Exception as e:
        logger.error(f"Error processing audio file: {str(e)}")
        raise e

def start_medical_transcription(bucket: str, key: str) -> str:
    """
    Start a medical transcription job
    """
    job_name = f"gocathlab-transcription-{uuid.uuid4().hex[:8]}-{int(time.time())}"
    
    media_uri = f"s3://{bucket}/{key}"
    
    # Determine media format from file extension
    file_extension = key.split('.')[-1].lower()
    media_format = {
        'wav': 'wav',
        'mp3': 'mp3',
        'mp4': 'mp4',
        'flac': 'flac',
        'm4a': 'mp4'
    }.get(file_extension, 'wav')
    
    try:
        response = transcribe_client.start_medical_transcription_job(
            MedicalTranscriptionJobName=job_name,
            LanguageCode='en-US',
            # Remove MediaSampleRateHertz to let Transcribe auto-detect
            MediaFormat=media_format,
            Media={
                'MediaFileUri': media_uri
            },
            OutputBucketName=os.environ['TRANSCRIPTION_RESULTS_BUCKET'],
            OutputKey=f"transcriptions/{job_name}/",
            Specialty='PRIMARYCARE',  # Only PRIMARYCARE is supported
            Type='CONVERSATION',  # or 'DICTATION' depending on audio type
            Settings={
                'ShowSpeakerLabels': True,
                'MaxSpeakerLabels': 4,
                'ChannelIdentification': False,
                'ShowAlternatives': True,
                'MaxAlternatives': 3
                # Removed VocabularyFilterMethod - not supported in Medical Transcribe
            }
        )
        
        logger.info(f"Started medical transcription job: {job_name}")
        return job_name
        
    except Exception as e:
        logger.error(f"Error starting transcription job: {str(e)}")
        raise e

def wait_for_transcription_completion(job_name: str, max_wait_time: int = 900) -> Optional[str]:
    """
    Wait for transcription job to complete and return the transcription text
    """
    start_time = time.time()
    
    while time.time() - start_time < max_wait_time:
        try:
            response = transcribe_client.get_medical_transcription_job(
                MedicalTranscriptionJobName=job_name
            )
            
            status = response['MedicalTranscriptionJob']['TranscriptionJobStatus']
            logger.info(f"Transcription job {job_name} status: {status}")
            
            if status == 'COMPLETED':
                # Get transcription results
                transcript_uri = response['MedicalTranscriptionJob']['Transcript']['TranscriptFileUri']
                return download_transcription_results(transcript_uri)
                
            elif status == 'FAILED':
                failure_reason = response['MedicalTranscriptionJob'].get('FailureReason', 'Unknown')
                raise Exception(f"Transcription job failed: {failure_reason}")
                
            # Wait before checking again
            time.sleep(30)
            
        except Exception as e:
            logger.error(f"Error checking transcription status: {str(e)}")
            raise e
    
    raise Exception(f"Transcription job {job_name} did not complete within {max_wait_time} seconds")

def download_transcription_results(transcript_uri: str) -> str:
    """
    Download transcription results from S3 URI
    """
    try:
        # Parse S3 URI properly
        # transcript_uri looks like: https://s3.us-east-1.amazonaws.com/bucket-name/path/to/file.json
        
        if transcript_uri.startswith('https://'):
            # Extract bucket and key from HTTPS URL
            # Format: https://s3.region.amazonaws.com/bucket-name/path/to/file.json
            # or: https://bucket-name.s3.region.amazonaws.com/path/to/file.json
            
            if '.s3.' in transcript_uri:
                # Format: https://bucket-name.s3.region.amazonaws.com/path/to/file.json
                parts = transcript_uri.replace('https://', '').split('/')
                bucket_and_region = parts[0]  # bucket-name.s3.region.amazonaws.com
                bucket = bucket_and_region.split('.s3.')[0]  # bucket-name
                key = '/'.join(parts[1:])  # path/to/file.json
            else:
                # Format: https://s3.region.amazonaws.com/bucket-name/path/to/file.json
                parts = transcript_uri.replace('https://', '').split('/')
                bucket = parts[1] if len(parts) > 1 else parts[0]  # bucket-name
                key = '/'.join(parts[2:]) if len(parts) > 2 else parts[1]  # path/to/file.json
        else:
            # Handle s3:// format
            uri_parts = transcript_uri.replace('s3://', '').split('/', 1)
            bucket = uri_parts[0]
            key = uri_parts[1] if len(uri_parts) > 1 else ''
        
        logger.info(f"Downloading transcription from bucket: {bucket}, key: {key}")
        
        # Download transcription file
        response = s3_client.get_object(Bucket=bucket, Key=key)
        transcript_data = json.loads(response['Body'].read().decode('utf-8'))
        
        # Extract transcript text
        transcript_text = transcript_data['results']['transcripts'][0]['transcript']
        
        logger.info(f"Downloaded transcription: {len(transcript_text)} characters")
        return transcript_text
        
    except Exception as e:
        logger.error(f"Error downloading transcription results: {str(e)}")
        logger.error(f"URI was: {transcript_uri}")
        raise e

def process_transcription_with_nlp(transcription_text: str, original_key: str) -> Dict[str, Any]:
    """
    Process transcription text with Amazon Comprehend Medical
    """
    results = {
        'timestamp': datetime.utcnow().isoformat(),
        'processing_id': str(uuid.uuid4()),
        'original_audio_file': original_key,
        'transcription_text': transcription_text,
        'entities': [],
        'phi_entities': [],
        'medications': [],
        'procedures': [],
        'diagnoses': [],
        'cardiovascular_entities': [],
        'cath_lab_specific': []
    }
    
    try:
        # Detect medical entities
        entity_response = comprehend_medical.detect_entities_v2(Text=transcription_text)
        results['entities'] = entity_response.get('Entities', [])
        
        # Detect PHI
        phi_response = comprehend_medical.detect_phi(Text=transcription_text)
        results['phi_entities'] = phi_response.get('Entities', [])
        
        # Process and categorize entities
        categorize_transcription_entities(results)
        
        # Extract cath lab specific information
        extract_cath_lab_entities(results)
        
        logger.info(f"Processed transcription with {len(results['entities'])} entities")
        
    except Exception as e:
        logger.error(f"Error in Comprehend Medical processing: {str(e)}")
        results['error'] = str(e)
    
    return results

def categorize_transcription_entities(results: Dict[str, Any]) -> None:
    """
    Categorize entities from transcription into relevant categories
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
                'attributes': entity.get('Attributes', []),
                'source': 'audio_transcription'
            })
        
        elif category == 'MEDICAL_CONDITION':
            results['diagnoses'].append({
                'text': entity.get('Text'),
                'confidence': entity.get('Score'),
                'type': entity_type,
                'attributes': entity.get('Attributes', []),
                'source': 'audio_transcription'
            })
        
        elif category == 'PROCEDURE':
            results['procedures'].append({
                'text': entity.get('Text'),
                'confidence': entity.get('Score'),
                'type': entity_type,
                'attributes': entity.get('Attributes', []),
                'source': 'audio_transcription'
            })

def extract_cath_lab_entities(results: Dict[str, Any]) -> None:
    """
    Extract cath lab specific entities and cardiovascular information
    """
    # Cath lab specific terms
    cath_lab_terms = [
        'catheter', 'guidewire', 'balloon', 'stent', 'contrast',
        'fluoroscopy', 'angiography', 'hemodynamics', 'pressure',
        'injection', 'vessel', 'artery', 'coronary', 'lad', 'rca', 'lcx',
        'stenosis', 'occlusion', 'thrombus', 'dissection',
        'complications', 'bleeding', 'hematoma', 'perforation',
        'access site', 'femoral', 'radial', 'closure device',
        'procedure time', 'contrast volume', 'radiation dose'
    ]
    
    # Cardiovascular procedures specific to cath lab
    cath_procedures = [
        'angioplasty', 'ptca', 'pci', 'stenting', 'atherectomy',
        'thrombectomy', 'balloon angioplasty', 'drug eluting stent',
        'bare metal stent', 'rotablation', 'cutting balloon',
        'intravascular ultrasound', 'ivus', 'oct', 'ffr',
        'fractional flow reserve', 'instantaneous wave free ratio'
    ]
    
    # Extract cath lab specific entities
    transcription_text = results['transcription_text'].lower()
    
    for term in cath_lab_terms + cath_procedures:
        if term in transcription_text:
            # Find all occurrences
            start_pos = 0
            while True:
                pos = transcription_text.find(term, start_pos)
                if pos == -1:
                    break
                
                results['cath_lab_specific'].append({
                    'text': term,
                    'category': 'cath_lab_equipment' if term in cath_lab_terms else 'cath_lab_procedure',
                    'position': pos,
                    'context': transcription_text[max(0, pos-50):pos+len(term)+50],
                    'source': 'audio_transcription'
                })
                
                start_pos = pos + 1
    
    # Also check existing entities for cardiovascular relevance
    cardio_keywords = [
        'coronary', 'cardiac', 'heart', 'cardiovascular', 'vessel',
        'artery', 'stenosis', 'ischemia', 'myocardial', 'angina'
    ]
    
    for entity in results['entities']:
        entity_text = entity.get('Text', '').lower()
        if any(keyword in entity_text for keyword in cardio_keywords):
            results['cardiovascular_entities'].append({
                'text': entity.get('Text'),
                'confidence': entity.get('Score'),
                'category': entity.get('Category'),
                'type': entity.get('Type'),
                'begin_offset': entity.get('BeginOffset'),
                'end_offset': entity.get('EndOffset'),
                'source': 'audio_transcription'
            })

def save_transcription_results(results: Dict[str, Any], original_key: str) -> None:
    """
    Save transcription and NLP results to S3
    """
    try:
        output_bucket = os.environ['NLP_OUTPUT_BUCKET']
        
        # Save detailed results
        output_key = f"transcriptions/{original_key.replace('.wav', '_transcription_results.json').replace('.mp3', '_transcription_results.json')}"
        
        s3_client.put_object(
            Bucket=output_bucket,
            Key=output_key,
            Body=json.dumps(results, indent=2),
            ContentType='application/json'
        )
        
        # Save summary for quick access
        summary = {
            'timestamp': results['timestamp'],
            'original_file': original_key,
            'transcription_length': len(results['transcription_text']),
            'total_entities': len(results['entities']),
            'cardiovascular_entities': len(results['cardiovascular_entities']),
            'cath_lab_entities': len(results['cath_lab_specific']),
            'medications_found': len(results['medications']),
            'procedures_found': len(results['procedures']),
            'diagnoses_found': len(results['diagnoses'])
        }
        
        summary_key = f"transcriptions/summaries/{original_key.replace('.wav', '_summary.json').replace('.mp3', '_summary.json')}"
        
        s3_client.put_object(
            Bucket=output_bucket,
            Key=summary_key,
            Body=json.dumps(summary, indent=2),
            ContentType='application/json'
        )
        
        logger.info(f"Transcription results saved to: {output_key}")
        logger.info(f"Summary saved to: {summary_key}")
        
    except Exception as e:
        logger.error(f"Error saving transcription results: {str(e)}")
        raise e