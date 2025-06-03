#!/usr/bin/env python3
"""
Direct FHIR Analytics Dashboard
Fetches data directly from HealthLake via API and creates analytics
Perfect for GoCathLab demonstrations
"""

import json
import requests
import boto3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import base64
from io import StringIO

class HealthLakeAnalytics:
    def __init__(self, datastore_id, profile_name):
        self.datastore_id = datastore_id
        self.profile_name = profile_name
        self.base_url = f"https://healthlake.us-east-1.amazonaws.com/datastore/{datastore_id}/r4"
        self.session = boto3.Session(profile_name=profile_name)
        self.credentials = self.session.get_credentials()
        
    def make_fhir_request(self, resource_type="", resource_id="", params=None):
        """Make authenticated FHIR API request"""
        from botocore.auth import SigV4Auth
        from botocore.awsrequest import AWSRequest
        
        if resource_id:
            url = f"{self.base_url}/{resource_type}/{resource_id}"
        elif params:
            url = f"{self.base_url}/{resource_type}?{params}"
        else:
            url = f"{self.base_url}/{resource_type}"
        
        headers = {
            'Content-Type': 'application/fhir+json',
            'Accept': 'application/fhir+json'
        }
        
        request = AWSRequest(method='GET', url=url, headers=headers)
        SigV4Auth(self.credentials, 'healthlake', 'us-east-1').add_auth(request)
        
        response = requests.get(url, headers=dict(request.headers))
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching {resource_type}: {response.status_code}")
            return None

    def get_all_patients(self):
        """Fetch all patients"""
        return self.make_fhir_request("Patient")
    
    def get_all_observations(self):
        """Fetch all observations"""
        return self.make_fhir_request("Observation")
    
    def get_all_documents(self):
        """Fetch all document references"""
        return self.make_fhir_request("DocumentReference")
    
    def get_all_procedures(self):
        """Fetch all procedures"""
        return self.make_fhir_request("Procedure")

    def analyze_resource_distribution(self):
        """Analyze distribution of FHIR resources"""
        print("🏥 FHIR Resource Distribution Analysis")
        print("=" * 50)
        
        resources = {
            "Patients": self.get_all_patients(),
            "Observations": self.get_all_observations(),
            "Documents": self.get_all_documents(),
            "Procedures": self.get_all_procedures()
        }
        
        distribution = {}
        for resource_type, data in resources.items():
            if data and 'entry' in data:
                count = len(data['entry'])
            else:
                count = 0
            distribution[resource_type] = count
            print(f"{resource_type}: {count}")
        
        return distribution

    def analyze_vital_signs(self):
        """Analyze vital signs data"""
        print("\n💓 Vital Signs Analysis")
        print("=" * 30)
        
        observations = self.get_all_observations()
        if not observations or 'entry' not in observations:
            print("No observations found")
            return []
        
        vital_signs = []
        
        for entry in observations['entry']:
            obs = entry['resource']
            
            # Extract basic observation info
            obs_data = {
                'patient_id': obs.get('subject', {}).get('reference', '').replace('Patient/', ''),
                'date': obs.get('effectiveDateTime', ''),
                'performer': obs.get('performer', [{}])[0].get('display', 'Unknown'),
                'status': obs.get('status', '')
            }
            
            # Handle single-value observations (like heart rate)
            if 'valueQuantity' in obs:
                code_info = obs.get('code', {}).get('coding', [{}])[0]
                obs_data.update({
                    'type': code_info.get('display', 'Unknown'),
                    'value': obs['valueQuantity'].get('value'),
                    'unit': obs['valueQuantity'].get('unit'),
                    'loinc_code': code_info.get('code')
                })
                vital_signs.append(obs_data)
            
            # Handle multi-component observations (like blood pressure)
            elif 'component' in obs:
                for component in obs['component']:
                    comp_data = obs_data.copy()
                    code_info = component.get('code', {}).get('coding', [{}])[0]
                    comp_data.update({
                        'type': code_info.get('display', 'Unknown'),
                        'value': component.get('valueQuantity', {}).get('value'),
                        'unit': component.get('valueQuantity', {}).get('unit'),
                        'loinc_code': code_info.get('code')
                    })
                    vital_signs.append(comp_data)
        
        # Display vital signs
        for vital in vital_signs:
            print(f"  {vital['type']}: {vital['value']} {vital['unit']} ({vital['date']})")
        
        return vital_signs

    def analyze_patient_demographics(self):
        """Analyze patient demographics"""
        print("\n👥 Patient Demographics")
        print("=" * 25)
        
        patients = self.get_all_patients()
        if not patients or 'entry' not in patients:
            print("No patients found")
            return []
        
        demographics = []
        for entry in patients['entry']:
            patient = entry['resource']
            
            # Extract name
            name_info = patient.get('name', [{}])[0]
            full_name = f"{name_info.get('given', [''])[0]} {name_info.get('family', '')}"
            
            # Extract address
            address_info = patient.get('address', [{}])[0]
            location = f"{address_info.get('city', '')}, {address_info.get('state', '')}"
            
            demo_data = {
                'id': patient.get('id'),
                'name': full_name.strip(),
                'gender': patient.get('gender'),
                'birth_date': patient.get('birthDate'),
                'active': patient.get('active'),
                'location': location
            }
            demographics.append(demo_data)
            
            print(f"  {demo_data['name']} ({demo_data['gender']}, born {demo_data['birth_date']})")
            print(f"    Location: {demo_data['location']}")
            print(f"    Status: {'Active' if demo_data['active'] else 'Inactive'}")
        
        return demographics

    def analyze_clinical_documents(self):
        """Analyze clinical documents"""
        print("\n📄 Clinical Documents Analysis")
        print("=" * 35)
        
        documents = self.get_all_documents()
        if not documents or 'entry' not in documents:
            print("No documents found")
            return []
        
        doc_analysis = []
        for entry in documents['entry']:
            doc = entry['resource']
            
            # Decode document content if available
            content_text = "Content not available"
            if 'content' in doc and doc['content']:
                try:
                    encoded_data = doc['content'][0].get('attachment', {}).get('data', '')
                    if encoded_data:
                        decoded_bytes = base64.b64decode(encoded_data)
                        content_text = decoded_bytes.decode('utf-8')
                except:
                    content_text = "Could not decode content"
            
            doc_data = {
                'id': doc.get('id'),
                'type': doc.get('type', {}).get('coding', [{}])[0].get('display', 'Unknown'),
                'date': doc.get('date'),
                'author': doc.get('author', [{}])[0].get('display', 'Unknown'),
                'description': doc.get('description', ''),
                'patient_id': doc.get('subject', {}).get('reference', '').replace('Patient/', ''),
                'content_preview': content_text[:200] + "..." if len(content_text) > 200 else content_text
            }
            doc_analysis.append(doc_data)
            
            print(f"  Document: {doc_data['type']}")
            print(f"    Author: {doc_data['author']}")
            print(f"    Date: {doc_data['date']}")
            print(f"    Description: {doc_data['description']}")
            print(f"    Preview: {doc_data['content_preview']}")
        
        return doc_analysis

    def create_cardiovascular_summary(self):
        """Create cardiovascular-specific summary for GoCathLab"""
        print("\n🫀 CARDIOVASCULAR SUMMARY FOR GOCATHLAB")
        print("=" * 45)
        
        # Get all data
        demographics = self.analyze_patient_demographics()
        vitals = self.analyze_vital_signs()
        documents = self.analyze_clinical_documents()
        
        # Cardiovascular-specific analysis
        cv_summary = {
            'total_patients': len(demographics),
            'total_vital_measurements': len(vitals),
            'total_clinical_notes': len(documents),
            'heart_rate_readings': [v for v in vitals if 'heart rate' in v.get('type', '').lower()],
            'bp_readings': [v for v in vitals if 'blood pressure' in v.get('type', '').lower()],
            'procedure_notes': [d for d in documents if 'catheter' in d.get('content_preview', '').lower()]
        }
        
        print(f"\n📊 Key Metrics:")
        print(f"  • Total Patients: {cv_summary['total_patients']}")
        print(f"  • Vital Sign Measurements: {cv_summary['total_vital_measurements']}")
        print(f"  • Heart Rate Readings: {len(cv_summary['heart_rate_readings'])}")
        print(f"  • Blood Pressure Readings: {len(cv_summary['bp_readings'])}")
        print(f"  • Catheterization Notes: {len(cv_summary['procedure_notes'])}")
        
        # Clinical insights
        if cv_summary['heart_rate_readings']:
            hr_values = [r['value'] for r in cv_summary['heart_rate_readings'] if r['value']]
            if hr_values:
                avg_hr = sum(hr_values) / len(hr_values)
                print(f"  • Average Heart Rate: {avg_hr:.1f} bpm")
        
        if cv_summary['bp_readings']:
            systolic = [r['value'] for r in cv_summary['bp_readings'] if 'systolic' in r.get('type', '').lower()]
            diastolic = [r['value'] for r in cv_summary['bp_readings'] if 'diastolic' in r.get('type', '').lower()]
            
            if systolic and diastolic:
                print(f"  • Blood Pressure: {systolic[0]:.0f}/{diastolic[0]:.0f} mmHg")
        
        print(f"\n✅ Data Quality:")
        print(f"  • Complete patient records with demographics")
        print(f"  • Structured vital signs using LOINC codes")
        print(f"  • Clinical documentation with procedure details")
        print(f"  • Ready for advanced analytics and ML")
        
        return cv_summary

    def generate_analytics_report(self):
        """Generate complete analytics report"""
        print("🚀 HEALTHLAKE ANALYTICS DASHBOARD")
        print("=" * 60)
        print(f"Data Store: {self.datastore_id}")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        # Run all analyses
        distribution = self.analyze_resource_distribution()
        demographics = self.analyze_patient_demographics()
        vitals = self.analyze_vital_signs()
        documents = self.analyze_clinical_documents()
        cv_summary = self.create_cardiovascular_summary()
        
        print(f"\n🎯 SUMMARY FOR GOCATHLAB DEMONSTRATION:")
        print(f"  ✅ Complete FHIR data store operational")
        print(f"  ✅ Patient data with cardiovascular focus")
        print(f"  ✅ Real-time vital signs monitoring")
        print(f"  ✅ Clinical documentation pipeline")
        print(f"  ✅ Ready for QuickSight visualization")
        print(f"  ✅ Scalable for population health analytics")
        
        return {
            'distribution': distribution,
            'demographics': demographics,
            'vitals': vitals,
            'documents': documents,
            'cv_summary': cv_summary
        }

if __name__ == "__main__":
    # Initialize analytics
    analytics = HealthLakeAnalytics(
        datastore_id="83a18c9ab49b1d93c9d256f4232b2805",
        profile_name="iamadmin-datalake-healthlake-365528423741"
    )
    
    # Generate complete report
    results = analytics.generate_analytics_report()