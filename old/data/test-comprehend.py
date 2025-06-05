import boto3
import json

def analyze_clinical_text():
    # Initialize Comprehend Medical client
    session = boto3.Session(profile_name='iamadmin-datalake-healthlake-365528423741', region_name='us-east-1')
    comprehend_medical = session.client('comprehendmedical')
    
    # Read clinical note
    with open('clinical-note.txt', 'r') as f:
        clinical_text = f.read()
    
    print("Analyzing clinical text with Comprehend Medical...")
    print("=" * 60)
    
    try:
        # Extract entities
        entities_response = comprehend_medical.detect_entities_v2(
            Text=clinical_text
        )
        
        print("MEDICAL ENTITIES FOUND:")
        print("-" * 30)
        
        # Group entities by category
        medications = []
        conditions = []
        procedures = []
        
        for entity in entities_response['Entities']:
            if entity['Category'] == 'MEDICATION':
                medications.append({
                    'text': entity['Text'],
                    'confidence': entity['Score']
                })
            elif entity['Category'] == 'MEDICAL_CONDITION':
                conditions.append({
                    'text': entity['Text'],
                    'confidence': entity['Score']
                })
            elif entity['Category'] == 'PROCEDURE':
                procedures.append({
                    'text': entity['Text'],
                    'confidence': entity['Score']
                })
        
        print(f"Medications found: {len(medications)}")
        for med in medications:
            print(f"  - {med['text']} (confidence: {med['confidence']:.2f})")
        
        print(f"\nConditions found: {len(conditions)}")
        for cond in conditions:
            print(f"  - {cond['text']} (confidence: {cond['confidence']:.2f})")
            
        print(f"\nProcedures found: {len(procedures)}")
        for proc in procedures:
            print(f"  - {proc['text']} (confidence: {proc['confidence']:.2f})")
        
        return entities_response
        
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    analyze_clinical_text()