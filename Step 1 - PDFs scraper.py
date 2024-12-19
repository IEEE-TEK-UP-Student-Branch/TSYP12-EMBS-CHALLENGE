import os
import yaml
import requests
from pathlib import Path
from datetime import datetime
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from tqdm import tqdm
from logger import ScraperLogger

class PDFScraper:
    def __init__(self, config_path="agent_config.yaml"):
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)
        
        self.logger = ScraperLogger()
        self.setup_directories()
        self.stats = {
            "queries_processed": 0,
            "pdfs_found": 0,
            "pdfs_downloaded": 0,
            "errors_encountered": 0
        }

    def setup_directories(self):
        base_path = Path(self.config['download_settings']['base_path'])
        for category in self.config['download_settings']['categories']:
            (base_path / category).mkdir(parents=True, exist_ok=True)

    def search_pdfs(self, query):
        self.logger.log_search_query(query)
        urls = []
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # Run in headless mode
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}+filetype:pdf"
        driver.get(search_url)
        
        # Extract PDF links
        links = driver.find_elements(By.TAG_NAME, 'a')
        for link in links:
            href = link.get_attribute('href')
            if href and "pdf" in href:
                urls.append(href)
                self.stats["pdfs_found"] += 1
        
        driver.quit()  # Close the browser
        return urls

    def validate_pdf(self, url):
        retries = 3
        for attempt in range(retries):
            try:
                response = requests.head(url, allow_redirects=True, timeout=10)
                if response.status_code == 200 and 'application/pdf' in response.headers.get('content-type', ''):
                    file_size = int(response.headers.get('content-length', 0)) / (1024 * 1024)  # Convert to MB
                    is_valid = file_size <= self.config['download_settings']['max_file_size_mb']
                    self.logger.log_validation_result(url, is_valid, 
                        None if is_valid else f"File size ({file_size}MB) exceeds limit")
                    return is_valid
                break  # Exit loop if successful
            except Exception as e:
                self.logger.log_error("Validation Error", str(e), {"url": url})
                self.stats["errors_encountered"] += 1
                if attempt < retries - 1:
                    time.sleep(10)  # Wait before retrying
                else:
                    return False
        return False

    def download_pdf(self, url, category):
        self.logger.log_download_attempt(url, category)
        try:
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                filename = url.split('/')[-1]
                if not filename.lower().endswith('.pdf'):
                    filename += '.pdf'
                
                save_path = Path(self.config['download_settings']['base_path']) / category / filename
                
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                self.logger.log_download_success(url, str(save_path))
                self.stats["pdfs_downloaded"] += 1
                return True
        except Exception as e:
            self.logger.log_download_error(url, e)
            self.stats["errors_encountered"] += 1
        return False

    def run(self):
        start_time = datetime.now()
        
        try:
            for query in tqdm(self.config['search_queries'], desc="Processing queries"):
                self.stats["queries_processed"] += 1
                urls = self.search_pdfs(query)
                
                for url in tqdm(urls, desc="Processing URLs", leave=False):
                    if self.validate_pdf(url):
                        category = next(
                            (cat for cat in self.config['download_settings']['categories'] 
                             if cat in query.lower()),
                            'research'  # default category
                        )
                        self.download_pdf(url, category)
        
        finally:
            # Log final statistics
            self.stats["duration"] = str(datetime.now() - start_time)
            self.logger.log_stats(self.stats)

if __name__ == "__main__":
    scraper = PDFScraper()
    scraper.run()
