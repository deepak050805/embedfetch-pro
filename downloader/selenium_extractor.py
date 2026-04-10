from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time

def extract_embedded_urls(page_url: str):
    """
    Uses Selenium to visit a page, extract iframe sources to find protected media urls.
    """
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    
    # Initialize Chrome driver
    CHROME_DRIVER_PATH = ChromeDriverManager().install()
    driver_service = Service(CHROME_DRIVER_PATH)
    driver = webdriver.Chrome(service=driver_service, options=options)
    
    urls = []
    try:
        driver.get(page_url)
        # Briefly wait for dynamic content/iframes to render
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Extract from typical embed iframe sources
        iframes = soup.find_all('iframe')
        for iframe in iframes:
            src = iframe.get('src')
            if src:
                urls.append(src)
        
        # Also grab standard video tags just in case
        video_tags = soup.find_all('video')
        for v in video_tags:
            src = v.get('src')
            if src:
                urls.append(src)

        return list(set(urls))
    except Exception as e:
        print(f"Error extracting URLs: {e}")
        return []
    finally:
        driver.quit()
