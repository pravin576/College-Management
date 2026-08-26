import urllib.request
import sys

BASE_URL = "http://localhost:8000"

HTML_PAGES = [
    "/",
    "/index.html",
    "/home.html",
    "/login.html",
    "/dashboard.html",
    "/students.html",
    "/faculty.html",
    "/hod.html",
    "/attendance.html",
    "/results.html",
    "/fees.html",
    "/timetable.html",
    "/notices.html",
    "/profile.html",
    "/settings.html",
    "/contact.html"
]

CSS_FILES = [
    "/css/style.css",
    "/css/index.css",
    "/css/login.css",
    "/css/dashboard.css",
    "/css/students.css",
    "/css/faculty.css",
    "/css/hod.css",
    "/css/attendance.css",
    "/css/results.css",
    "/css/fees.css",
    "/css/timetable.css",
    "/css/notices.css",
    "/css/profile.css",
    "/css/settings.css",
    "/css/contact.css",
    "/css/home.css"
]

JS_FILES = [
    "/js/script.js",
    "/js/index.js",
    "/js/login.js",
    "/js/dashboard.js",
    "/js/students.js",
    "/js/faculty.js",
    "/js/hod.js",
    "/js/attendance.js",
    "/js/results.js",
    "/js/fees.js",
    "/js/timetable.js",
    "/js/notices.js",
    "/js/profile.js",
    "/js/settings.js",
    "/js/contact.js",
    "/js/home.js"
]

IMAGE_FILES = [
    "/images/logo.jpg",
    "/images/img1.jpg",
    "/images/img2.jpg",
    "/images/img3.jpg",
    "/images/img4.jpg"
]

def test_assets():
    print("--- TESTING ALL PAGES, CSS, JS AND IMAGE ASSETS ---")

    print("\n1. Testing HTML Pages...")
    for page in HTML_PAGES:
        url = f"{BASE_URL}{page}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            ct = resp.headers.get("Content-Type", "")
            assert resp.status == 200, f"Failed page {page}: {resp.status}"
            print(f"  [OK] Page '{page}' -> Status: 200, Content-Type: {ct}")

    print("\n2. Testing CSS Files & Content-Type Headers...")
    for css in CSS_FILES:
        url = f"{BASE_URL}{css}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            ct = resp.headers.get("Content-Type", "")
            assert resp.status == 200, f"Failed CSS {css}: {resp.status}"
            assert "text/css" in ct, f"CSS {css} has invalid Content-Type: {ct}"
            print(f"  [OK] CSS '{css}' -> Status: 200, Content-Type: {ct}")

    print("\n3. Testing JS Files & Content-Type Headers...")
    for js in JS_FILES:
        url = f"{BASE_URL}{js}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            ct = resp.headers.get("Content-Type", "")
            assert resp.status == 200, f"Failed JS {js}: {resp.status}"
            assert "javascript" in ct, f"JS {js} has invalid Content-Type: {ct}"
            print(f"  [OK] JS '{js}' -> Status: 200, Content-Type: {ct}")

    print("\n4. Testing Image Files...")
    for img in IMAGE_FILES:
        url = f"{BASE_URL}{img}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            ct = resp.headers.get("Content-Type", "")
            assert resp.status == 200, f"Failed Image {img}: {resp.status}"
            assert "image" in ct, f"Image {img} has invalid Content-Type: {ct}"
            print(f"  [OK] Image '{img}' -> Status: 200, Content-Type: {ct}")

    print("\n==================================================")
    print("ALL HTML, CSS, JS, AND IMAGE ASSETS VERIFIED 100%!")
    print("==================================================")

if __name__ == "__main__":
    test_assets()
