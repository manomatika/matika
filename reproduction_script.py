import requests

session = requests.Session()

# 1. Login
login_payload = {
    "email": "admin",
    "password": "adminpassword"
}
# Follow redirects is True by default for POST in requests if it gets a 303, 
# but let's see where it goes.
response = session.post("http://127.0.0.1:8000/login", data=login_payload, allow_redirects=False)

print(f"Login status: {response.status_code}")
print(f"Login location: {response.headers.get('Location')}")

if response.status_code == 303:
    next_url = response.headers.get('Location')
    if next_url.startswith("/"):
        next_url = "http://127.0.0.1:8000" + next_url
    
    response = session.get(next_url, allow_redirects=False)
    print(f"Followed to: {next_url}")
    print(f"Final status: {response.status_code}")
    print(f"Final location: {response.headers.get('Location')}")
    # print(response.text[:500])
