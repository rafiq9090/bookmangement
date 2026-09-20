"""
Automated API Endpoints Smoke Test
Tests public and authenticated endpoints against the running Django server.
"""
import sys
import requests

BASE_URL = "http://127.0.0.1:8000"

def print_result(method, path, status_code, expected_status, note=""):
    passed = status_code in expected_status if isinstance(expected_status, (list, tuple)) else status_code == expected_status
    mark = " [PASS] " if passed else " [FAIL] "
    color_code = "\033[92m" if passed else "\033[91m"
    reset = "\033[0m"
    print(f"{color_code}{mark}{reset} {method:<6} {path:<38} Status: {status_code:<4} {note}")
    return passed

def main():
    print(f"\n==========================================")
    print(f" Testing API Endpoints on {BASE_URL}")
    print(f"==========================================\n")

    # 1. Check server connectivity
    try:
        r = requests.get(f"{BASE_URL}/api/schema/", timeout=5)
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Error: Could not connect to {BASE_URL}.")
        print("Please ensure the development server is running: python manage.py runserver\n")
        sys.exit(1)

    all_passed = True

    # 2. Public / Documentation Endpoints
    print("--- 1. Documentation & Discovery Endpoints ---")
    all_passed &= print_result("GET", "/api/schema/", requests.get(f"{BASE_URL}/api/schema/").status_code, 200)
    all_passed &= print_result("GET", "/api/docs/", requests.get(f"{BASE_URL}/api/docs/").status_code, 200, "(Swagger UI)")
    all_passed &= print_result("GET", "/api/redoc/", requests.get(f"{BASE_URL}/api/redoc/").status_code, 200, "(ReDoc)")

    # 3. Public Catalog Endpoints
    print("\n--- 2. Public Catalog & Listings Endpoints ---")
    all_passed &= print_result("GET", "/api/v1/books/", requests.get(f"{BASE_URL}/api/v1/books/").status_code, 200)
    all_passed &= print_result("GET", "/api/v1/books/categories/", requests.get(f"{BASE_URL}/api/v1/books/categories/").status_code, 200)
    all_passed &= print_result("GET", "/api/v1/listings/", requests.get(f"{BASE_URL}/api/v1/listings/").status_code, 200)

    # 4. Authentication flow
    print("\n--- 3. User Authentication Flow ---")
    test_email = "tester_smoke@example.com"
    test_password = "SecurePassword@123"

    # Try register
    reg_resp = requests.post(f"{BASE_URL}/api/v1/accounts/register/", json={
        "email": test_email,
        "password": test_password,
        "first_name": "Smoke",
        "last_name": "Tester"
    })
    print_result("POST", "/api/v1/accounts/register/", reg_resp.status_code, [201, 400], "(201 Created or 400 if user exists)")

    # Login to get JWT
    login_resp = requests.post(f"{BASE_URL}/api/v1/accounts/login/", json={
        "email": test_email,
        "password": test_password
    })
    all_passed &= print_result("POST", "/api/v1/accounts/login/", login_resp.status_code, 200)

    tokens = login_resp.json() if login_resp.status_code == 200 else {}
    access_token = tokens.get("access")

    if not access_token:
        print("❌ Could not obtain access token. Skipping authenticated endpoints.")
        return

    headers = {"Authorization": f"Bearer {access_token}"}

    # 5. Authenticated Endpoints
    print("\n--- 4. Authenticated User Endpoints ---")
    all_passed &= print_result("GET", "/api/v1/accounts/me/", requests.get(f"{BASE_URL}/api/v1/accounts/me/", headers=headers).status_code, 200)
    all_passed &= print_result("GET", "/api/v1/accounts/addresses/", requests.get(f"{BASE_URL}/api/v1/accounts/addresses/", headers=headers).status_code, 200)
    all_passed &= print_result("GET", "/api/v1/listings/my/", requests.get(f"{BASE_URL}/api/v1/listings/my/", headers=headers).status_code, 200)
    all_passed &= print_result("GET", "/api/v1/orders/cart/", requests.get(f"{BASE_URL}/api/v1/orders/cart/", headers=headers).status_code, 200)
    all_passed &= print_result("GET", "/api/v1/orders/", requests.get(f"{BASE_URL}/api/v1/orders/", headers=headers).status_code, 200)
    all_passed &= print_result("GET", "/api/v1/messaging/conversations/", requests.get(f"{BASE_URL}/api/v1/messaging/conversations/", headers=headers).status_code, 200)
    all_passed &= print_result("GET", "/api/v1/payments/balance/", requests.get(f"{BASE_URL}/api/v1/payments/balance/", headers=headers).status_code, 200)
    all_passed &= print_result("GET", "/api/v1/payments/ledger/", requests.get(f"{BASE_URL}/api/v1/payments/ledger/", headers=headers).status_code, 200)

    print(f"\n==========================================")
    if all_passed:
        print(" 🎉 All checked endpoints are WORKING properly!")
    else:
        print(" ⚠️ Some endpoints returned unexpected status codes.")
    print(f"==========================================\n")

if __name__ == "__main__":
    main()
