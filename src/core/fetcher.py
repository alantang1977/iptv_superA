import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import os
from src.utils.logger import logger

class SourceFetcher:
    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        })

    def _is_valid_url(self, url):
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False

    def fetch(self, url):
        try:
            if not self._is_valid_url(url):
                if os.path.exists(url):
                    with open(url, 'r', encoding='utf-8') as f:
                        return f.read()
                return None

            resp = self.session.get(
                url,
                timeout=self.config['performance']['timeout'],
                stream=True
            )
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {str(e)}")
            return None

    def fetch_all(self, urls):
        results = {}
        with ThreadPoolExecutor(max_workers=self.config['performance']['threads']) as executor:
            future_to_url = {
                executor.submit(self.fetch, url): url
                for url in urls
            }
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    data = future.result()
                    if data:
                        results[url] = data
                except Exception as e:
                    logger.error(f"Error processing {url}: {str(e)}")
        
        return results
