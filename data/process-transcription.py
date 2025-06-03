import boto3
import json
import base64
from datetime import datetime

def process_transcription_to_fhir():
    # Simulated transcription text (from above)
    transcription_text = """Patient John Doe underwent left heart catheterization. 
The procedure was performed via right femoral approach. Coronary angiography 
revealed normal coronary arteries with no significant stenosis. Left ventricular 
ejection fraction is estimated at sixty percent. Patient tolerated the procedure 
well with no complications."""
    
    # Properly encode as Base64
    encoded_text = base64.b64encode(transcription_text.encode('utf-8')).decode('utf-8')
    
    # Create a DocumentReference FHIR resource from the transcription
    document_reference = {
        "resourceType": "DocumentReference",
        "status": "current",
        "type": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "11488-4",
                    "display": "Consult note"
                }
            ]
        },
        "subject": {
            "reference": "Patient/684b7be0-40ff-40c9-aac1-fcbbe85819e1"
        },
        "date": datetime.now().isoformat() + "Z",
        "author": [
            {
                "display": "Dr. Johnson, Interventional Cardiologist"
            }
        ],
        "description": "Transcribed procedure note from cardiac catheterization",
        "content": [
            {
                "attachment": {
                    "contentType": "text/plain",
                    "data": encoded_text
                }
            }
        ],
        "context": {
            "period": {
                "start": "2025-06-01T14:00:00Z",
                "end": "2025-06-01T15:30:00Z"
            }
        }
    }
    
    # Save to file for upload
    with open('transcription-document.json', 'w') as f:
        json.dump(document_reference, f, indent=2)
    
    print("Created DocumentReference from transcription:")
    print(f"Encoded text length: {len(encoded_text)} characters")
    
    return document_reference

if __name__ == "__main__":
    process_transcription_to_fhir()