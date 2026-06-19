import requests

url = "https://investchat-api.onrender.com/api/v1/auth/login"
r = requests.post(url, json={"email":"test@test.com", "password":"test"})
if r.status_code == 200:
    token = r.json()["access_token"]
    print("Login successful")
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("test.txt", b"dummy content")}
    # Need a project id to upload a document. Let's create one.
    r_proj = requests.post("https://investchat-api.onrender.com/api/v1/projects", headers=headers, json={"name":"Test Project"})
    if r_proj.status_code in [200, 201]:
        proj_id = r_proj.json()["id"]
        print(f"Created project: {proj_id}")
        r_up = requests.post(f"https://investchat-api.onrender.com/api/v1/projects/{proj_id}/documents", headers=headers, files=files, data={"doc_type":"other"})
        print(f"Upload Status: {r_up.status_code}")
        print(f"Upload Response: {r_up.text}")
    else:
        print("Project creation failed:", r_proj.text)
else:
    print("Login failed:", r.status_code, r.text)
