import urllib.request, json
req = urllib.request.Request('http://127.0.0.1:8000/api/login', 
                             data=json.dumps({'username':'bhau141','password':'password','role':'Student'}).encode('utf-8'), 
                             headers={'Content-Type': 'application/json'})
try:
    res = urllib.request.urlopen(req)
    print(res.read())
except urllib.error.HTTPError as e:
    print(e.read())
