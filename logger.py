import logging
import logging.config
import yaml
from pathlib import Path
import os
from datetime import datetime

class ScraperLogger:
    def __init__(self):
        # Create a unique logs directory for each run
        self.run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.logs_dir = Path(f"logs/{self.run_id}")
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Load logging configuration
        with open("logging_config.yaml", 'r') as f:
            config = yaml.safe_load(f)
            # Update log file paths in the config
            for handler in config['handlers'].values():
                if 'filename' in handler:
                    handler['filename'] = str(self.logs_dir / Path(handler['filename']).name)
            logging.config.dictConfig(config)

        # Initialize different loggers
        self.main_logger = logging.getLogger('scraper')
        self.llm_logger = logging.getLogger('scraper.llm')
        self.downloads_logger = logging.getLogger('scraper.downloads')
        self.error_logger = logging.getLogger('scraper.errors')

    def log_llm_conversation(self, agent_name, prompt, response):
        """Log LLM conversations"""
        self.llm_logger.debug(
            f"\nAgent: {agent_name}\n"
            f"Prompt: {prompt}\n"
            f"Response: {response}\n"
            f"{'='*50}"
        )

    def log_download_attempt(self, url, category):
        """Log when a download is attempted"""
        self.downloads_logger.info(f"Attempting download - URL: {url}, Category: {category}")

    def log_download_success(self, url, filepath):
        """Log successful downloads"""
        self.downloads_logger.info(f"Successfully downloaded - URL: {url} to {filepath}")

    def log_download_error(self, url, error):
        """Log download errors"""
        self.error_logger.error(f"Download failed - URL: {url}, Error: {str(error)}")
        self.downloads_logger.error(f"Download failed - URL: {url}")

    def log_search_query(self, query):
        """Log search queries"""
        self.main_logger.info(f"Executing search query: {query}")

    def log_validation_result(self, url, is_valid, reason=None):
        """Log PDF validation results"""
        if is_valid:
            self.main_logger.info(f"Validated PDF: {url}")
        else:
            self.main_logger.warning(f"Invalid PDF: {url} - Reason: {reason}")

    def log_error(self, error_type, error_message, details=None):
        """Log general errors"""
        self.error_logger.error(
            f"Error Type: {error_type}\n"
            f"Message: {error_message}\n"
            f"Details: {details if details else 'No additional details'}"
        )

    def log_stats(self, stats_dict):
        """Log scraping statistics"""
        stats_message = "\nScraping Statistics:\n" + "\n".join(
            f"{k}: {v}" for k, v in stats_dict.items()
        )
        self.main_logger.info(stats_message)
