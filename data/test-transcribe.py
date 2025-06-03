import boto3
import json
import time
import uuid

def test_transcribe_medical():
    # Initialize Transcribe client
    session = boto3.Session(profile_name='iamadmin-datalake-healthlake-365528423741', region_name='us-east-1')
    transcribe = session.client('transcribe')
    
    # For demo purposes, we'll show how to set up a transcription job
    # In real scenario, you'd have an audio file in S3
    
    job_name = f"medical-transcription-{uuid.uuid4()}"
    
    print("Setting up Medical Transcription Job...")
    print(f"Job Name: {job_name}")
    print("=" * 50)
    
    # This is how you would start a real transcription job:
    transcription_config = {
        'JobName': job_name,
        'LanguageCode': 'en-US',
        'MediaFormat': 'wav',  # or mp3, mp4, etc.
        'Media': {
            'MediaFileUri': 's3://healthlake-carba-365528423741/medical-audio.wav'
        },
        'Settings': {
            'VocabularyName': 'medical-vocabulary',  # optional custom vocabulary
            'ShowSpeakerLabels': True,
            'MaxSpeakerLabels': 2
        },
        'Specialty': 'CARDIOLOGY',  # Perfect for GoCathLab!
        'Type': 'CONVERSATION'  # or DICTATION
    }
    
    print("Transcription Configuration:")
    print(json.dumps(transcription_config, indent=2))
    
    # Simulated transcription result for demonstration
    simulated_transcript = {
        "jobName": job_name,
        "results": {
            "transcripts": [
                {
                    "transcript": "Patient John Doe underwent left heart catheterization. The procedure was performed via right femoral approach. Coronary angiography revealed normal coronary arteries with no significant stenosis. Left ventricular ejection fraction is estimated at sixty percent. Patient tolerated the procedure well with no complications."
                }
            ],
            "speaker_labels": {
                "speakers": 2,
                "segments": [
                    {
                        "start_time": "0.0",
                        "end_time": "15.5",
                        "speaker_label": "spk_0",
                        "items": [
                            {
                                "start_time": "0.0",
                                "end_time": "15.5",
                                "speaker_label": "spk_0"
                            }
                        ]
                    }
                ]
            }
        }
    }
    
    print("\nSimulated Transcription Result:")
    print("-" * 30)
    print(simulated_transcript['results']['transcripts'][0]['transcript'])
    
    return simulated_transcript

if __name__ == "__main__":
    result = test_transcribe_medical()