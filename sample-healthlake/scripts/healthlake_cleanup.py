#!/usr/bin/env python3
"""
HealthLake Cleanup Script
Deletes all resources from a HealthLake datastore
"""

import boto3
import json
import sys
import time
from datetime import datetime

def get_healthlake_client():
    """Initialize HealthLake client"""
    session = boto3.Session(profile_name='1iamadmin-datalake-healthlake-365528423741', region_name='us-east-1')
    return session.client('healthlake')

def search_all_resources(client, datastore_id, resource_type):
    """Search for all resources of a given type"""
    try:
        response = client.search_with_get(
            DatastoreId=datastore_id,
            ResourceType=resource_type
        )
        
        if 'ResourceDocument' in response:
            data = json.loads(response['ResourceDocument'])
            return data.get('entry', [])
        return []
    except Exception as e:
        print(f"Error searching {resource_type}: {e}")
        return []

def delete_resource(client, datastore_id, resource_type, resource_id):
    """Delete a specific resource"""
    try:
        response = client.delete_resource(
            DatastoreId=datastore_id,
            ResourceType=resource_type,
            ResourceId=resource_id
        )
        return True
    except Exception as e:
        print(f"Error deleting {resource_type}/{resource_id}: {e}")
        return False

def cleanup_datastore(datastore_id, dry_run=True):
    """Clean up all resources from HealthLake datastore"""
    client = get_healthlake_client()
    
    # Resource types to clean up (in order of dependencies)
    resource_types = [
        'Observation',      # Delete observations first
        'Procedure',        # Then procedures
        'Patient'           # Finally patients (referenced by others)
    ]
    
    total_deleted = 0
    
    print(f"{'DRY RUN: ' if dry_run else ''}Cleaning up HealthLake datastore: {datastore_id}")
    print("=" * 60)
    
    for resource_type in resource_types:
        print(f"\n🔍 Searching for {resource_type} resources...")
        
        resources = search_all_resources(client, datastore_id, resource_type)
        print(resources)
        
        if not resources:
            print(f"   ✅ No {resource_type} resources found")
            continue
            
        print(f"   📋 Found {len(resources)} {resource_type} resources")
        
        for entry in resources:
            resource = entry.get('resource', {})
            resource_id = resource.get('id')
            
            if not resource_id:
                print(f"   ⚠️  Skipping {resource_type} without ID")
                continue
            
            # Show resource details
            if resource_type == 'Patient':
                name = resource.get('name', [{}])[0]
                display_name = f"{' '.join(name.get('given', []))} {name.get('family', '')}"
                print(f"   👤 Patient: {resource_id} ({display_name.strip()})")
            elif resource_type == 'Observation':
                code = resource.get('code', {}).get('coding', [{}])[0]
                code_display = code.get('display', 'Unknown')
                print(f"   📊 Observation: {resource_id} ({code_display})")
            elif resource_type == 'Procedure':
                code = resource.get('code', {}).get('coding', [{}])[0]
                code_display = code.get('display', 'Unknown')
                print(f"   🏥 Procedure: {resource_id} ({code_display})")
            
            if not dry_run:
                success = delete_resource(client, datastore_id, resource_type, resource_id)
                if success:
                    print(f"      ✅ Deleted {resource_type}/{resource_id}")
                    total_deleted += 1
                    time.sleep(0.1)  # Small delay to avoid rate limiting
                else:
                    print(f"      ❌ Failed to delete {resource_type}/{resource_id}")
            else:
                print(f"      🔄 Would delete {resource_type}/{resource_id}")
                total_deleted += 1
    
    print(f"\n{'DRY RUN: ' if dry_run else ''}Summary:")
    print(f"{'Would delete' if dry_run else 'Deleted'} {total_deleted} resources total")
    
    if dry_run:
        print("\n⚠️  This was a DRY RUN. No resources were actually deleted.")
        print("Run with --execute flag to perform actual deletion.")
    else:
        print("\n✅ Cleanup completed!")

def main():
    # Get datastore ID
    if len(sys.argv) > 1:
        datastore_id = sys.argv[1]
    else:
        # Try to get from Terraform output
        import subprocess
        try:
            result = subprocess.run(['terraform', 'output', '-raw', 'healthlake_datastore_id'], 
                                  capture_output=True, text=True, check=True)
            datastore_id = result.stdout.strip()
        except:
            print("Please provide datastore ID as argument or run from Terraform directory")
            sys.exit(1)
    
    # Check for execute flag
    dry_run = '--execute' not in sys.argv
    
    if dry_run:
        print("🔍 DRY RUN MODE - No actual deletions will be performed")
        print("Add --execute flag to perform actual cleanup")
        print()
    
    cleanup_datastore(datastore_id, dry_run=dry_run)

if __name__ == "__main__":
    main()