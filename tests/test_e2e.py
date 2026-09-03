import urllib.request, json
BASE_URL = 'http://127.0.0.1:8000/api'
def req(path, payload):
    print("SENDING", path)
    r = urllib.request.Request(BASE_URL + path, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
    try:
        res = urllib.request.urlopen(r)
        print(f'{path} SUCCESS:', res.read().decode())
    except urllib.error.HTTPError as e:
        print(f'{path} ERROR:', e.code, e.read().decode())

req('/register', {'role':'Student','name':'testuser4','email':'testuser4@test.com','mobile':'4234567890','studentId':'test4','year':'First Year','username':'testuser4','password':'password','confirmPassword':'password', 'dob': '2000-01-01'})
req('/login', {'username':'testuser4','password':'password','role':'Student'})
req('/forgot-password', {'action':'verify', 'role':'Student', 'identifier': 'testuser4'})
req('/forgot-password', {'action':'reset', 'username':'testuser4', 'newPassword':'newpassword', 'confirmPassword':'newpassword', 'verificationValue':'2000-01-01'})
req('/login', {'username':'testuser4','password':'newpassword','role':'Student'})
