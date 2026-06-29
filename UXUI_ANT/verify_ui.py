# Automated UI/UX Validation Script using Playwright
# This script opens the local index.html, simulates full user interactions across multiple courses, and captures screenshots.

import os
import sys
import time
from playwright.sync_api import sync_playwright

def run():
    # Setup screenshots directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ss_dir = os.path.join(base_dir, 'screenshots')
    os.makedirs(ss_dir, exist_ok=True)
    
    html_path = f"file://{os.path.join(base_dir, 'index.html')}"
    print(f"[*] Starting UI/UX Verification on: {html_path}")
    
    with sync_playwright() as p:
        # Launch browser headlessly
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 850})
        page = context.new_page()
        
        # Monitor console errors
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        
        # --- PHASE 1: DIRECT ROUTING & DEV WIDGET TEST ---
        print("[1] Loading Landing Page...")
        page.goto(html_path)
        page.wait_for_timeout(500)
        page.screenshot(path=os.path.join(ss_dir, "01_landing.png"))
        
        # Test Onboarding hash navigation
        print("[2] Navigating to Onboarding via Dev Links...")
        page.locator("#dev-quick-nav >> text=온보딩").click()
        page.wait_for_timeout(500)
        page.screenshot(path=os.path.join(ss_dir, "02_onboarding.png"))
        
        # Test Library hash navigation
        print("[3] Jumping directly to Library...")
        page.locator("#dev-quick-nav >> text=라이브러리").click()
        page.wait_for_timeout(500)
        page.screenshot(path=os.path.join(ss_dir, "03_library.png"))
        
        # --- PHASE 2: ALGORITHM COURSE VERIFICATION ---
        print("[4] Starting Algorithm Course...")
        # Start "알고리즘적 사고와 문제해결력" Course
        page.locator(".course-card:has-text('알고리즘적 사고') .btn-start-course").click()
        page.wait_for_timeout(800)
        page.screenshot(path=os.path.join(ss_dir, "04_algorithm_study_p1.png"))
        
        # Step through binary search
        print("    -> Simulating binary search steps...")
        page.locator("#btn-bin-step").click()
        page.wait_for_timeout(300)
        page.locator("#btn-bin-step").click()
        page.wait_for_timeout(300)
        page.screenshot(path=os.path.join(ss_dir, "04_algorithm_study_p1_searched.png"))
        
        # Go to Choice page
        page.locator("#btn-page-action").click() # Continue
        page.wait_for_timeout(500)
        page.screenshot(path=os.path.join(ss_dir, "04_algorithm_study_p2.png"))
        
        # Solve choice
        page.locator(".quiz-card >> text=O(log N)").click()
        page.locator("#btn-page-action").click() # Check
        page.wait_for_timeout(300)
        page.locator("#btn-page-action").click() # Continue
        page.wait_for_timeout(500)
        
        # Exit back to library
        page.locator("#btn-study-exit").click()
        page.wait_for_timeout(500)
        
        # --- PHASE 3: QUANTUM COMPUTING COURSE VERIFICATION ---
        print("[5] Starting Quantum Computing Course...")
        page.locator(".course-card:has-text('양자 컴퓨팅 입문') .btn-start-course").click()
        page.wait_for_timeout(800)
        page.screenshot(path=os.path.join(ss_dir, "05_quantum_study_p1.png"))
        
        # Drag probability slider
        print("    -> Adjusting Bloch sphere probability slider...")
        page.locator("#qc-prob-slider").fill("80")
        page.wait_for_timeout(300)
        page.screenshot(path=os.path.join(ss_dir, "05_quantum_study_p1_tuned.png"))
        
        # Perform measurement collapse
        print("    -> Testing qubit state collapse measurement...")
        page.locator("#btn-qc-measure").click()
        page.wait_for_timeout(800)
        page.screenshot(path=os.path.join(ss_dir, "05_quantum_study_p1_collapsed.png"))
        
        # Exit and check dashboard
        page.locator("#btn-study-exit").click()
        page.wait_for_timeout(300)
        page.locator("#dev-quick-nav >> text=대시보드").click()
        page.wait_for_timeout(500)
        page.screenshot(path=os.path.join(ss_dir, "06_dashboard.png"))
        
        browser.close()
        
    print("\n[+] Multicourse Verification Completed!")
    print(f"[+] Screenshots successfully saved to: {ss_dir}")
    if console_errors:
        print(f"[!] Warning: {len(console_errors)} console errors detected:")
        for err in console_errors:
            print(f"    - {err}")
    else:
        print("[+] Success: Zero browser console errors found.")

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"[-] Execution failed: {e}")
        sys.exit(1)
