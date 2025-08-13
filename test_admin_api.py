#!/usr/bin/env python3
"""
Test script for admin API endpoints
"""

import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def test_admin_api():
    print("🔐 Testing Admin API Authentication System")
    print("=" * 50)
    
    # Test 1: Login with correct credentials
    print("1. Testing admin login...")
    login_response = requests.post(f"{BASE_URL}/admin/login", json={
        "username": "admin",
        "password": "password"
    })
    
    if login_response.status_code == 200:
        login_data = login_response.json()
        if login_data['success']:
            session_token = login_data['session_token']
            print(f"✅ Login successful! Token: {session_token[:16]}...")
        else:
            print(f"❌ Login failed: {login_data['message']}")
            return
    else:
        print(f"❌ Login request failed with status {login_response.status_code}")
        return
    
    # Test 2: Check admin status
    print("\n2. Testing admin status check...")
    status_response = requests.get(f"{BASE_URL}/admin/status", headers={
        "Authorization": f"Bearer {session_token}"
    })
    
    if status_response.status_code == 200:
        status_data = status_response.json()
        if status_data['authenticated']:
            print("✅ Admin status check successful - authenticated")
        else:
            print("❌ Admin status check failed - not authenticated")
    else:
        print(f"❌ Status check failed with status {status_response.status_code}")
    
    # Test 3: Test protected endpoint (database stats)
    print("\n3. Testing protected endpoint access...")
    try:
        stats_response = requests.get(f"{BASE_URL}/admin/tracked-products", headers={
            "Authorization": f"Bearer {session_token}"
        })
        
        if stats_response.status_code == 200:
            stats_data = stats_response.json()
            print(f"✅ Protected endpoint access successful - found {len(stats_data.get('products', []))} tracked products")
        else:
            print(f"❌ Protected endpoint access failed with status {stats_response.status_code}")
    except Exception as e:
        print(f"❌ Protected endpoint test failed: {e}")
    
    # Test 4: Test access without authentication
    print("\n4. Testing access without authentication...")
    unauth_response = requests.get(f"{BASE_URL}/admin/tracked-products")
    
    if unauth_response.status_code == 401:
        print("✅ Unauthenticated access correctly blocked")
    else:
        print(f"❌ Unauthenticated access not blocked - status: {unauth_response.status_code}")
    
    # Test 5: Test logout
    print("\n5. Testing admin logout...")
    logout_response = requests.post(f"{BASE_URL}/admin/logout", headers={
        "Authorization": f"Bearer {session_token}"
    })
    
    if logout_response.status_code == 200:
        logout_data = logout_response.json()
        if logout_data['success']:
            print("✅ Logout successful")
        else:
            print(f"❌ Logout failed: {logout_data['message']}")
    else:
        print(f"❌ Logout failed with status {logout_response.status_code}")
    
    # Test 6: Test access after logout
    print("\n6. Testing access after logout...")
    post_logout_response = requests.get(f"{BASE_URL}/admin/status", headers={
        "Authorization": f"Bearer {session_token}"
    })
    
    if post_logout_response.status_code == 200:
        post_logout_data = post_logout_response.json()
        if not post_logout_data['authenticated']:
            print("✅ Session correctly invalidated after logout")
        else:
            print("❌ Session still valid after logout")
    else:
        print(f"❌ Post-logout status check failed with status {post_logout_response.status_code}")
    
    print("\n🎉 Admin API testing completed!")

if __name__ == "__main__":
    try:
        test_admin_api()
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure the FastAPI server is running on http://127.0.0.1:8000")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")