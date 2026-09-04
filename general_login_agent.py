import os
import time
import requests
import json
import re
import base64
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def load_memory():
    try:
        with open("C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\memory.json", 'r') as f:
            return json.load(f)
    except:
        return {}

def save_memory(memory):
    try:
        with open("C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\memory.json", 'w') as f:
            json.dump(memory, f, indent=2)
    except:
        pass

def find_login_url(site_name):
    known = {
        "vtop": "https://vtop.vit.ac.in/vtop/initialProcess",
        "github": "https://github.com/login",
        "facebook": "https://www.facebook.com/login",
        "gmail": "https://accounts.google.com",
        "google": "https://accounts.google.com",
        "twitter": "https://x.com/login",
        "x": "https://x.com/login",
        "linkedin": "https://www.linkedin.com/login",
        "instagram": "https://www.instagram.com/accounts/login/"
    }
    name_clean = site_name.strip().lower()
    if name_clean in known:
        return known[name_clean]
        
    # Search DuckDuckGo for the login URL
    try:
        import urllib.parse
        q = urllib.parse.quote(f"{site_name} login page")
        res = requests.get(f"https://html.duckduckgo.com/html/?q={q}", headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if res.status_code == 200:
            # Parse DDG html search results
            href_matches = re.findall(r'href="([^"]+)"', res.text)
            for href in href_matches:
                if "uddg=" in href:
                    encoded_url = href.split("uddg=")[1].split("&")[0]
                    decoded_url = urllib.parse.unquote(encoded_url)
                    if "login" in decoded_url.lower() or "signin" in decoded_url.lower() or "auth" in decoded_url.lower():
                        return decoded_url
            # Fallback to the first non-ddg result
            for href in href_matches:
                if "uddg=" in href:
                    encoded_url = href.split("uddg=")[1].split("&")[0]
                    return urllib.parse.unquote(encoded_url)
    except Exception as e:
        print(f"Error searching login URL: {e}")
        
    return f"https://www.{site_name}.com"

def get_elements_metadata(driver):
    elements = []
    # Query input and button tags
    tags = driver.find_elements(By.XPATH, "//input | //button | //a[@role='button']")
    for idx, el in enumerate(tags):
        try:
            tag_name = el.tag_name
            type_attr = el.get_attribute("type") or ""
            id_attr = el.get_attribute("id") or ""
            name_attr = el.get_attribute("name") or ""
            placeholder = el.get_attribute("placeholder") or ""
            class_attr = el.get_attribute("class") or ""
            text = el.text or ""
            
            # Simple unique locator strategy builder
            xpath = f"//input[@id='{id_attr}']" if id_attr else (f"//input[@name='{name_attr}']" if name_attr else f"(//input)[{idx+1}]")
            if tag_name == "button":
                xpath = f"//button[@id='{id_attr}']" if id_attr else (f"//button[@name='{name_attr}']" if name_attr else f"(//button)[{idx+1}]")
                
            elements.append({
                "index": idx,
                "tag": tag_name,
                "type": type_attr,
                "id": id_attr,
                "name": name_attr,
                "placeholder": placeholder,
                "class": class_attr,
                "text": text,
                "xpath_guess": xpath
            })
        except:
            continue
    return elements

def query_gemini_selectors(screenshot_path, elements, api_key):
    try:
        with open(screenshot_path, "rb") as img_file:
            encoded_image = base64.b64encode(img_file.read()).decode('utf-8')
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        
        prompt = (
            "Analyze the attached login webpage screenshot and the JSON list of HTML elements present on the page.\n"
            "Identify the correct elements for filling the credentials and logging in.\n"
            "Return ONLY a valid JSON object matching the schema below, without markdown blocks or explanation.\n"
            "Schema:\n"
            "{\n"
            "  \"username_selector\": \"exact xpath or css selector to click/type username\",\n"
            "  \"password_selector\": \"exact xpath or css selector to click/type password\",\n"
            "  \"submit_selector\": \"exact xpath or css selector to click submit/login button\",\n"
            "  \"captcha_img_selector\": \"xpath or selector for CAPTCHA image element (null if none)\",\n"
            "  \"captcha_input_selector\": \"xpath or selector for CAPTCHA input box (null if none)\"\n"
            "}\n\n"
            f"HTML elements metadata:\n{json.dumps(elements, indent=2)}"
        )
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inlineData": {"mimeType": "image/png", "data": encoded_image}}
                ]
            }]
        }
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        res.raise_for_status()
        text = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        
        # Clean JSON blocks
        if text.startswith("```json"):
            text = text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif text.startswith("```"):
            text = text.split("```", 1)[1].split("```", 1)[0].strip()
            
        return json.loads(text)
    except Exception as e:
        print(f"Error querying Gemini for selectors: {e}")
        return None

def solve_captcha(image_path, api_key):
    try:
        with open(image_path, "rb") as img_file:
            encoded_string = base64.b64encode(img_file.read()).decode('utf-8')
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Solve this text CAPTCHA. Respond ONLY with the CAPTCHA code, no other text."},
                    {"inlineData": {"mimeType": "image/png", "data": encoded_string}}
                ]
            }]
        }
        res = requests.post(url, headers=headers, json=payload, timeout=12)
        res.raise_for_status()
        text = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        return re.sub(r'\s+', '', text)
    except Exception as e:
        print(f"Captcha solving error: {e}")
        return None

def run_general_login_flow(site_name, username, password, api_key):
    url = find_login_url(site_name)
    print(f"Target login URL found: {url}")
    
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    
    try:
        driver.get(url)
        time.sleep(5.0) # Wait for page load
        
        # Screenshot the current login view
        screenshot_path = "C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\temp_login_page.png"
        driver.save_screenshot(screenshot_path)
        
        # Get active elements metadata
        elements = get_elements_metadata(driver)
        
        # Let Gemini decide selectors
        selectors = query_gemini_selectors(screenshot_path, elements, api_key)
        if not selectors:
            raise Exception("Gemini could not identify login form elements.")
            
        print(f"Gemini identified selectors: {selectors}")
        
        # Locate username
        u_sel = selectors.get("username_selector")
        p_sel = selectors.get("password_selector")
        s_sel = selectors.get("submit_selector")
        
        if not u_sel or not p_sel or not s_sel:
            raise Exception("Incomplete selectors returned by Gemini.")
            
        uname_el = driver.find_element(By.XPATH, u_sel) if u_sel.startswith("//") else driver.find_element(By.CSS_SELECTOR, u_sel)
        passwd_el = driver.find_element(By.XPATH, p_sel) if p_sel.startswith("//") else driver.find_element(By.CSS_SELECTOR, p_sel)
        submit_el = driver.find_element(By.XPATH, s_sel) if s_sel.startswith("//") else driver.find_element(By.CSS_SELECTOR, s_sel)
        
        # CAPTCHA solving (if requested by selectors)
        c_img_sel = selectors.get("captcha_img_selector")
        c_in_sel = selectors.get("captcha_input_selector")
        
        if c_img_sel and c_in_sel:
            c_img_el = driver.find_element(By.XPATH, c_img_sel) if c_img_sel.startswith("//") else driver.find_element(By.CSS_SELECTOR, c_img_sel)
            c_in_el = driver.find_element(By.XPATH, c_in_sel) if c_in_sel.startswith("//") else driver.find_element(By.CSS_SELECTOR, c_in_sel)
            
            captcha_crop_path = "C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\temp_captcha_crop.png"
            c_img_el.screenshot(captcha_crop_path)
            
            solved_code = solve_captcha(captcha_crop_path, api_key)
            if solved_code:
                c_in_el.send_keys(solved_code)
                print(f"Auto-filled CAPTCHA code: {solved_code}")
                
        # Send inputs
        uname_el.clear()
        uname_el.send_keys(username)
        passwd_el.clear()
        passwd_el.send_keys(password)
        
        time.sleep(0.5)
        submit_el.click()
        
        print("Login button clicked, waiting for landing page...")
        time.sleep(6.0)
        
        # Capture post-login verification screenshot
        post_screenshot = f"C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\uploads\\{site_name}_dashboard.png"
        os.makedirs(os.path.dirname(post_screenshot), exist_ok=True)
        driver.save_screenshot(post_screenshot)
        
        return True, f"Successfully logged into {site_name.upper()} Sir! Dashboard screenshot saved to your uploads folder."
        
    except Exception as e:
        print(f"General login error: {e}")
        return False, str(e)
    finally:
        driver.quit()
