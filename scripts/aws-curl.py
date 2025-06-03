#!/usr/bin/env python3
import boto3
import requests
import json
import sys
import hashlib
import hmac
from datetime import datetime
from urllib.parse import urlparse

def sign_aws_request(method, url, data=None, profile_name=None):
    # Get AWS credentials
    session = boto3.Session(profile_name=profile_name)
    credentials = session.get_credentials()
    
    if not credentials:
        raise Exception("No AWS credentials found")
    
    # Parse URL
    parsed_url = urlparse(url)
    host = parsed_url.netloc
    path = parsed_url.path
    
    # AWS signature variables
    service = 'healthlake'
    region = 'us-east-1'
    algorithm = 'AWS4-HMAC-SHA256'
    
    # Create timestamp
    t = datetime.utcnow()
    amz_date = t.strftime('%Y%m%dT%H%M%SZ')
    date_stamp = t.strftime('%Y%m%d')
    
    # Prepare payload
    if data:
        if isinstance(data, str):
            if data.startswith('@'):
                # Handle @filename format
                with open(data[1:], 'r') as f:
                    payload = f.read()
            elif data.endswith('.json'):
                # Handle filename.json format
                with open(data, 'r') as f:
                    payload = f.read()
            else:
                # Handle direct JSON string
                payload = data
        else:
            payload = json.dumps(data)
    else:
        payload = ''
    
    # Create canonical headers
    canonical_headers = f'content-type:application/fhir+json\n'
    canonical_headers += f'host:{host}\n'
    canonical_headers += f'x-amz-date:{amz_date}\n'
    
    signed_headers = 'content-type;host;x-amz-date'
    
    # Add security token if present
    if credentials.token:
        canonical_headers += f'x-amz-security-token:{credentials.token}\n'
        signed_headers += ';x-amz-security-token'
    
    # Create payload hash
    payload_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    
    # Create canonical request
    canonical_request = f'{method}\n{path}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}'
    
    # Create string to sign
    credential_scope = f'{date_stamp}/{region}/{service}/aws4_request'
    string_to_sign = f'{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode()).hexdigest()}'
    
    # Calculate signature
    def get_signature_key(key, date_stamp, region_name, service_name):
        k_date = hmac.new(('AWS4' + key).encode('utf-8'), date_stamp.encode('utf-8'), hashlib.sha256).digest()
        k_region = hmac.new(k_date, region_name.encode('utf-8'), hashlib.sha256).digest()
        k_service = hmac.new(k_region, service_name.encode('utf-8'), hashlib.sha256).digest()
        k_signing = hmac.new(k_service, b'aws4_request', hashlib.sha256).digest()
        return k_signing
    
    signing_key = get_signature_key(credentials.secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
    
    # Create authorization header
    authorization_header = f'{algorithm} Credential={credentials.access_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}'
    
    # Prepare headers
    headers = {
        'Content-Type': 'application/fhir+json',
        'X-Amz-Date': amz_date,
        'Authorization': authorization_header,
        'Accept': 'application/fhir+json'
    }
    
    if credentials.token:
        headers['X-Amz-Security-Token'] = credentials.token
    
    return headers, payload

def make_curl_command(method, url, data_file=None, profile_name=None):
    try:
        headers, payload = sign_aws_request(method, url, data_file, profile_name)
        
        # Build curl command
        curl_cmd = f'curl -X {method} "{url}"'
        
        for key, value in headers.items():
            curl_cmd += f' \\\n    -H "{key}: {value}"'
        
        if payload and method.upper() != 'GET':
            # For demonstration, show the data inline
            curl_cmd += f' \\\n    -d \'{payload}\''
        
        print("Generated CURL command:")
        print("=" * 50)
        print(curl_cmd)
        print("=" * 50)
        
        # Also make the actual request
        print("\nMaking actual request...")
        
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers)
        elif method.upper() == 'POST':
            response = requests.post(url, headers=headers, data=payload)
        else:
            response = requests.request(method, url, headers=headers, data=payload)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body: {response.text}")
        
        return response
        
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 aws-curl.py METHOD URL [DATA_FILE]")
        print("Example: python3 aws-curl.py GET 'https://healthlake.us-east-1.amazonaws.com/datastore/ID/r4/Patient'")
        print("Example: python3 aws-curl.py POST 'https://healthlake.us-east-1.amazonaws.com/datastore/ID/r4/Patient' sample-patient.json")
        sys.exit(1)
    
    method = sys.argv[1].upper()
    url = sys.argv[2]
    data_file = sys.argv[3] if len(sys.argv) > 3 else None
    profile = 'iamadmin-datalake-healthlake-365528423741'
    
    make_curl_command(method, url, data_file, profile)