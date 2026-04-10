from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, User, Role, pwd_context

def test():
    client = TestClient(app)
    # Log in
    resp = client.post("/login", data={"email": "admin@matika.local", "password": "adminpassword"}, follow_redirects=False)
    print(f"Login status: {resp.status_code}")
    print(f"Login headers: {resp.headers}")
    cookies = resp.cookies

    # Access roles
    resp = client.get("/admin/roles", cookies=cookies)
    print(f"Roles status: {resp.status_code}")
    if resp.status_code == 200:
        print("Successfully accessed /admin/roles")
    else:
        print(f"Response text: {resp.text}")

if __name__ == "__main__":
    test()
