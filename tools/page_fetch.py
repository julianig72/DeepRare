import time
import chardet
import string
import re

import requests
from fake_useragent import UserAgent
from bs4 import BeautifulSoup

from contextlib import contextmanager
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

from tools.llm_agent import Summarize_Agent

# Global variables
ua = UserAgent()

_driver = None
MAX_WAIT = 8

# browser_session
@contextmanager
def browser_session(args):
    global _driver
    chrome_options = Options()
    if not args.visualize:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_experimental_option('prefs', {
        'profile.managed_default_content_settings.images': 2,
        'profile.managed_default_content_settings.stylesheet': 2
        })
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument(f"user-agent={ua.random}")
    chrome_options.page_load_strategy = 'eager'  # Imporve page load speed
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-application-cache")
    chrome_options.add_argument("--window-size=1550,1000")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--incognito")

    
    if _driver is None:
        _driver = webdriver.Chrome(options=chrome_options, service=Service(args.chrome_driver))
    try:
        yield _driver
    except Exception as e:
        _driver.quit()
        _driver = None
        raise e


def detect_and_decode(content):
    """Detect encoding and decode content"""
    # Detect PDF
    if content.startswith(b'%PDF'):
        raise ValueError("PDF content detected")

    # Use chardet to detect encoding
    encoding_info = chardet.detect(content)
    detected_encoding = encoding_info['encoding'] or 'utf-8'
    confidence = encoding_info['confidence']

    try:
        # If confidence is high, use the detected encoding
        if confidence > 0.75:
            return content.decode(detected_encoding, errors='replace')
        # If confidence is low, try multiple encodings
        else:
            for enc in ['utf-8', 'gbk', 'gb2312', 'latin1']:
                try:
                    return content.decode(enc, errors='strict')
                except UnicodeDecodeError:
                    continue
            return content.decode('utf-8', errors='replace')
    except Exception as e:
        raise ValueError(f"Error in decoding: {str(e)}")
    

def is_garbled_text(text, threshold=0.3):
    """Detect garbled text"""
    if not text:
        return True
    printable_count = sum(1 for c in text if c in string.printable or c.isspace())
    return (printable_count / len(text)) < threshold


def content_is_valid(html, min_text_length=500, min_links=3):
    """Determine if the content is valid"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # Basic structure check
    if re.search(r'%PDF|endobj\r\nstartxref', html[:1000]):
        print("Detected PDF content")
        return False

    # Detect garbled text
    sample_text = BeautifulSoup(html, 'html.parser').get_text()[:1000]
    if is_garbled_text(sample_text):
        print("Detected garbled text")
        return False
    
    # Rule 1: Text length check
    main_text = soup.get_text(separator=' ', strip=True)
    
    if len(main_text) < min_text_length:
        return False
    
    # Rule 2: Content container check
    content_containers = soup.find_all(['article', 'div', 'section', 'main'])
    content_containers = [c for c in content_containers if 
                         re.search(r'(content|body|article|post)', ' '.join(c.get('class', [])))]
    if not content_containers:
        return False
    
    # Rule 3: Anti-scraping keywords check
    anti_scraping_keywords = ['enable javascript', 'cloudflare', '验证', '请开启JS']
    if any(keyword in html.lower() for keyword in anti_scraping_keywords):
        return False
    
    # Rule 4: Link count check
    links = soup.find_all('a', href=True)
    if len(links) < min_links:
        return False
    
    return True

def fast_content_check(html):
    """Fast content check"""
    # Check if the HTML is too short or missing body tag
    if len(html) < 1000 or not re.search(r'<body.*?>', html, re.I):
        return False
    
    # Check if the HTML is mostly printable
    text_sample = re.sub(r'<[^>]+>', '', html[:2000])
    printable_ratio = sum(1 for c in text_sample if c in string.printable)/len(text_sample)
    return printable_ratio > 0.7


def get_webpage_text(args, url, screenshot=False):
    headers = {'User-Agent': ua.random}
    
    # Fist try to get the content via requests
    try:
        # raise requests.exceptions.RequestException()
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        
        # Check content type
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' not in content_type:
            print(f"Not HTML: {content_type}")
            raise requests.exceptions.RequestException()

        # Decode content
        try:
            decoded_html = detect_and_decode(response.content)
        except ValueError as e:
            print(f"Error decoding: {str(e)}")
            raise requests.exceptions.RequestException()
        
        
        # Fast content check
        if content_is_valid(decoded_html):
            return extract_main_content(decoded_html)
        
        # Requests content check failed, try Selenium
        # print("Requests content check failed, try Selenium...")
        raise requests.exceptions.RequestException()
    
    except requests.exceptions.RequestException as e:
        try:
            return get_via_selenium(args, url)
        except Exception as selenium_err:
            print(f"Selenium fallback also failed: {selenium_err}")
            return ""
    
def get_via_selenium(args, url):
    with browser_session(args) as driver: 
        try:
            
            driver.get(url)
            
            # Max wait time
            max_wait = MAX_WAIT
            start_time = time.time()
            
            # First phase: wait for page load
            try:
                WebDriverWait(driver, 3).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except TimeoutException:
                pass
            
            # Second phase: wait for content to load
            content_loaded = False
            while time.time() - start_time < max_wait and not content_loaded:
                # Check if the page is fully loaded
                locators = [
                    (By.TAG_NAME, 'article'),
                    (By.CSS_SELECTOR, 'div.content, main, section'),
                    (By.XPATH, '//p[string-length(text()) > 100]'),
                    (By.ID, 'main-content')
                ]
                
                for locator in locators:
                    try:
                        element = driver.find_element(*locator)
                        if element.is_displayed():
                            content_loaded = True
                            break
                    except:
                        continue
                
                # Check if the page contains certain keywords
                if not content_loaded and any(keyword in driver.page_source.lower() 
                                           for keyword in ['article', 'paragraph', 'section']):
                    content_loaded = True
                
                time.sleep(0.5)
            
            # # Third phase: wait for content to load
            # WebDriverWait(driver, 3).until(
            #     lambda d: len(d.find_elements(By.TAG_NAME, 'p')) >= 3 or
            #             len(d.find_elements(By.CSS_SELECTOR, 'div.article-body')) >= 1
            # )
            
            # Use JavaScript to scroll to the bottom of the page
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            # time.sleep(1)
            # driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            selenium_html = driver.page_source
            
            # Check if the content is valid
            if content_is_valid(selenium_html):
                text = driver.execute_script("return document.body.innerText;")
                return text
            
            return ""
            
        except Exception as e:
            print(f"Selenium Failed: {str(e)}")
            # Try to get the content using JavaScript
            last_html = driver.execute_script("return document.documentElement.outerHTML;")
            if content_is_valid(last_html):
                return extract_main_content(last_html)
            return ""
def extract_main_content(html):
    return BeautifulSoup(html, 'html.parser').get_text('\n', strip=True)


def fetch_page_content_and_summarize(args, url, mini_handler, screenshot):

    text = get_webpage_text(args, url, screenshot).replace("\n", " ").strip()
    return Summarize_Agent(text, mini_handler)
     


# Use example
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--visualize", action="store_true", help="If set, the browser will be visible")
    
    args = parser.parse_args()
    
    test_urls = [
        f"https://www.malacards.org/card/mandibulofacial_dysostosis_guion_almeida_type",  
        f"https://fdna.com/health/resource-center/mandibulofacial-dysostosis-guion-almeida-type-mfdga/", 
    ]
    
    for url in test_urls:
        print(f"Processing: {url}")
        print(get_webpage_text(args, url))
        print("\n" + "="*80 + "\n")