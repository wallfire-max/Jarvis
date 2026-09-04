import os
import time
import requests
import json
import re
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

def save_vtop_das_to_deadlines(parsed_das):
    memory = load_memory()
    deadlines = memory.setdefault("deadlines", [])
    
    # Avoid exact duplicates
    existing_titles = [d.get("title", "").lower() for d in deadlines]
    
    added_count = 0
    for da in parsed_das:
        title = f"{da['course']} - {da['assignment']}"
        if title.lower() not in existing_titles:
            due = da['due_date']
            deadlines.append({
                "id": len(deadlines) + 1,
                "title": title,
                "due_date": due,
                "status": da['status']
            })
            added_count += 1
            
    if added_count > 0:
        save_memory(memory)
    return added_count

def solve_captcha(image_path, api_key):
    import base64
    try:
        with open(image_path, "rb") as img_file:
            encoded_string = base64.b64encode(img_file.read()).decode('utf-8')
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Solve this simple text CAPTCHA. Respond ONLY with the CAPTCHA code text, no spaces, no explanation, no markdown."},
                    {"inlineData": {"mimeType": "image/png", "data": encoded_string}}
                ]
            }]
        }
        res = requests.post(url, headers=headers, json=payload, timeout=12)
        res.raise_for_status()
        text = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        return re.sub(r'\s+', '', text)
    except Exception as e:
        print(f"Error solving CAPTCHA via Gemini: {e}")
        return None

def run_vtop_login(username, password, api_key):
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    options.add_argument("--mute-audio")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    
    try:
        print("Navigating to VTOP...")
        driver.get("https://vtop.vit.ac.in/vtop/initialProcess")
        wait = WebDriverWait(driver, 15)
        
        try:
            student_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Student') or contains(., 'STUDENT') or contains(@class, 'student')]")))
            student_btn.click()
            print("Student login clicked.")
            time.sleep(2.0)
        except Exception as e:
            print("Could not find Student button:", e)
            
        uname_input = wait.until(EC.presence_of_element_located((By.NAME, "uname")))
        passwd_input = driver.find_element(By.NAME, "passwd")
        
        captcha_img = None
        for selector in ["captcha_img", "captchaImg", "captcha"]:
            try:
                captcha_img = driver.find_element(By.ID, selector)
                break
            except:
                pass
        if not captcha_img:
            try:
                captcha_img = driver.find_element(By.XPATH, "//img[contains(@src, 'captcha') or contains(@class, 'captcha')]")
            except:
                pass
                
        if not captcha_img:
            raise Exception("Failed to locate CAPTCHA image element.")
            
        captcha_path = "C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\captcha.png"
        os.makedirs(os.path.dirname(captcha_path), exist_ok=True)
        captcha_img.screenshot(captcha_path)
        print("CAPTCHA image saved.")
        
        solved_code = solve_captcha(captcha_path, api_key)
        if not solved_code:
            raise Exception("Failed to solve CAPTCHA via Vision API.")
        print(f"Solved CAPTCHA: {solved_code}")
        
        uname_input.send_keys(username)
        passwd_input.send_keys(password)
        
        captcha_input = None
        for selector in ["captchaRating", "captcha", "captcha_input"]:
            try:
                captcha_input = driver.find_element(By.NAME, selector)
                break
            except:
                pass
        if not captcha_input:
            captcha_input = driver.find_element(By.ID, "captchaRating")
            
        captcha_input.send_keys(solved_code)
        
        submit_btn = driver.find_element(By.XPATH, "//button[@type='submit' or contains(., 'Submit') or contains(., 'Login')]")
        submit_btn.click()
        print("Submit clicked. Waiting for dashboard...")
        
        time.sleep(5.0)
        
        if "login" in driver.current_url.lower() or "initialprocess" in driver.current_url.lower():
            return False, "CAPTCHA incorrect or credentials failed. Retrying..."
            
        print("Login successful! Navigating to Digital Assignments page...")
        driver.get("https://vtop.vit.ac.in/vtop/academics/common/StudentDA")
        time.sleep(3.0)
        
        screenshot_path = "C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\uploads\\vtop_da_dashboard.png"
        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
        driver.save_screenshot(screenshot_path)
        
        try:
            rows = driver.find_elements(By.XPATH, "//table//tr")
            parsed_das = []
            for row in rows[1:]:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 4:
                    course = cols[1].text.strip()
                    da_name = cols[2].text.strip()
                    due_date = cols[3].text.strip()
                    status = cols[4].text.strip() if len(cols) > 4 else "Unknown"
                    parsed_das.append({
                        "course": course,
                        "assignment": da_name,
                        "due_date": due_date,
                        "status": status
                    })
            
            if parsed_das:
                added = save_vtop_das_to_deadlines(parsed_das)
                return True, f"Successfully logged into VTOP and parsed {len(parsed_das)} digital assignments, Sir! Added {added} new deadlines."
            else:
                return True, "Successfully logged into VTOP, but found no active Digital Assignments."
        except Exception as table_err:
            print(f"Table parse error: {table_err}")
            return True, "Successfully logged into VTOP, but failed to parse the DA table. A screenshot has been captured."
            
    except Exception as e:
        print(f"Automation error: {e}")
        return False, str(e)
    finally:
        driver.quit()
