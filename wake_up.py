from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

def wake_up():
    print("Starting browser...")
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        url = "https://auction1-pto-check-yoco6lndlsgq4pubmtqw3h.streamlit.app/"
        print(f"Visiting {url}...")
        driver.get(url)
        
        # Wait for potential redirects and initial loading
        time.sleep(5)
        
        title = driver.title
        print(f"Page title: {title}")
        
        # Wait more to ensure Streamlit app loads
        time.sleep(10)
        
        print("Successfully visited the app.")
        
    except Exception as e:
        print(f"Error occurred: {e}")
        
    finally:
        driver.quit()
        print("Browser closed.")

if __name__ == "__main__":
    wake_up()
