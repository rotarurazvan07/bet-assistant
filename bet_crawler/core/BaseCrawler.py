from abc import ABC

from bet_framework.SettingsManager import settings_manager
from bet_framework.WebScraper import WebScraper


class BaseCrawler(ABC):
    def __init__(self):
         self.web_scraper = WebScraper(
             custom_cookies=settings_manager.settings['webdriver']['custom_cookies'],
             custom_headers=settings_manager.settings['webdriver']['custom_headers'],
             request_failed_keywords=settings_manager.settings['webdriver']['request_failed_keywords'],
             request_retry_keywords=settings_manager.settings['webdriver']['request_retry_keywords'],
             retry_count=settings_manager.settings['webdriver']['retry_count']
         )
