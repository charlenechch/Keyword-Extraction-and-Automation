import sys
import json
from playwright.sync_api import sync_playwright

# CONFIG 
SAP_LOGIN_URL = "https://hcm10preview.sapsf.com/sf/home?bplte_company=sarawakeneT1"
SLOW_MO_MS = 300  # slow down actions so you can see what's happening

# MAIN AGENT 
def autofill_sapsf(meta: dict):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            channel="msedge",  
            slow_mo=300
        )
        context = browser.new_context()
        page = context.new_page()

        # A. LOGIN (HUMAN)
        page.goto(SAP_LOGIN_URL)

        # log in manually (SSO/MFA/PDPA)
        page.pause()  

        # B. Home → View My Learning
        page.wait_for_selector("text=View My Learning", timeout=60000)
        page.click("text=View My Learning")

        # C. Open top-right menu 
        # This is the icon next to the bell / profile (grid icon)
        page.wait_for_selector("button[aria-label='Actions']", timeout=60000)
        page.click("button[aria-label='Actions']")

        # D. Click Learning Administration
        page.wait_for_selector("text=Learning Administration", timeout=30000)
        page.click("text=Learning Administration")

        # E. SWITCH TO IFRAME (CRITICAL)
        # SAP Learning Admin loads inside an iframe.
        # This grabs the FIRST iframe on the page.
        frame = page.frame_locator("iframe")

        # F. SIDEBAR NAVIGATION
        frame.locator("text=Learning Activities").wait_for(timeout=60000)
        frame.locator("text=Learning Activities").click()

        frame.locator("text=Items").wait_for(timeout=30000)
        frame.locator("text=Items").click()

        # F. ADD NEW ITEM
        frame.locator("text=Add New").wait_for(timeout=30000)
        frame.locator("text=Add New").click()

        # G. AUTOFILL (EXAMPLES)
        # Autofill SAP SF: New Item
        # Title
        page.get_by_label("Title").fill(meta["Program Title"])

        # Training Provider
        page.get_by_label("Training Provider").fill(
            meta.get("Training Organiser", "")
        )

        # HRD Fund (Yes / No)
        page.get_by_label("HRD Fund").click()

        if meta.get("HRDC Certified", "").lower() == "yes":
            page.get_by_role("option", name="(Yes)").click()
        else:
            page.get_by_role("option", name="(No)").click()


        # H. HUMAN REVIEW (NO AUTO-SUBMIT)
        page.pause()  # Admin reviews & saves/submits manually

        browser.close()


# ========= CLI ENTRY (FOR subprocess.Popen) =========
if __name__ == "__main__":
    """
    Called like:
    python autofill_sapsf.py "<json_meta_string>"
    """

    if len(sys.argv) < 2:
        print("ERROR: Missing meta JSON")
        sys.exit(1)

    meta = json.loads(sys.argv[1])
    autofill_sapsf(meta)
