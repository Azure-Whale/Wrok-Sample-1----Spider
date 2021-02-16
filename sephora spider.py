from logging import error
import time
import math
import json
from typing import Dict
import requests
from bs4 import BeautifulSoup as bs
import scrapy
from common import create_logger,SPIDER_LOG_FOLDER

from scrapy_selenium import SeleniumRequest
from scrapy_splash import SplashRequest
from selenium import webdriver

from shutil import which

from ..items import ProductItem
from .base_spider import BaseSpider
from .base_spider import BaseInDBSpider, BaseSpider

STORE_NAME = 'Sephora'
LOG = create_logger(__name__, log_folder=SPIDER_LOG_FOLDER)

class SephoraFullSpider(BaseSpider):
    """
    To run the spider, it requires the ChromeDrive and you should set the DRIVER_PATH after you download it
    Command:
    
    screapy crawl sephora_spider

    """
    name = 'sephora_spider'
    allowed_domains = ["www.sephora.com"]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        name = 'sephora_spider'
        self.base_url = "https://www.sephora.com"
        options = webdriver.ChromeOptions()
        options.add_argument('headless')
        self.headers = {
            'user-agent':
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_1_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Safari/537.36"
        }
        custom_settings = {
            "SELENIUM_DRIVER_EXECUTABLE_PATH":
            which('chromedriver')
        }
        self.driver = webdriver.Chrome(custom_settings['SELENIUM_DRIVER_EXECUTABLE_PATH'])


    def close_spider(self):
        # close the webdriver when the spider finishes its jobs
        self.driver.quit()
        self.driver.close()


    def start_requests(self):
        """
        start on brand page and iterate all brands

        yield: Request to brand page
        """
        # Get into the brand page which contains all brand hrefs    
        self.driver.get("https://www.sephora.com/brands-list")
        self.view_all(0.5)
        # get soup of all brands
        content = self.driver.page_source
        brand_soup = bs(content, "html.parser")
        # get all brand
        all_brands = brand_soup.find_all('a', {"class": "css-xyl2uf"})
        # To close the register model, refresh the current site (it only happens when it is first visit)
        first_visit = 1
        for brand in all_brands:
            brand = self.base_url + brand.attrs['href']
            if first_visit == 1:
                self.driver.get(brand)
                first_visit -= 1
            yield scrapy.Request(url=brand,
                                  callback=self.parse_brand,
                                  headers=self.headers)

    def parse_brand(self, response):
        """
        Iterate all pages in a single brand and collect basic features of all products for each single page
        
        yield: Request to product page of each collected product
        """
        # use drive open current page
        self.driver.get(response.url)
        # time inerval bettwen scroll down time
        SCROLL_PAUSE_TIME = 0.5
        # number of product that can be viewed in single page of sephora
        sephora_page_view = 60
        # view all products from up to down so that the sys can get access to all lazy loaded items
        self.view_all(0.5)
        # get soup form current page
        content = self.driver.page_source
        product_soup = bs(content, "html.parser")
        # get number of pages can be viewed in current page
        num_pages = product_soup.find('span', {
            "data-at": "number_of_products"
        }).text.replace(' products', '')
        num_pages = math.ceil((int(num_pages) / sephora_page_view))
        # iterate each page to view all products under one brand
        for page in range(1, num_pages + 1):
            # first visit doesn't need refresh
            if page > 1:
                self.driver.get(response.url + '?currentPage={}'.format(page))
            self.view_all(1)
            content = self.driver.page_source
            product_soup = bs(content, "html.parser")
            all_products = product_soup.find_all('div',
                                                 {"class": "css-12egk0t"})
            # iterate each product and collect all related features
            for product in all_products:
                # fetch product url from category page
                product_url = product.find('a', {
                    "class": "css-ix8km1"
                })
                if not product_url:
                    continue
                else:
                    product_url = self.base_url + product_url.attrs['href'].split()[0]
                yield SeleniumRequest(url=product_url,
                                      callback=self._create_product_item,
                                      headers=self.headers)


    def view_all(self, SCROLL_PAUSE_TIME):
        """
        Go down to the botton of page
        """
        self.driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight*(1/6));")
        time.sleep(SCROLL_PAUSE_TIME)
        self.driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight*(2/6));")
        time.sleep(SCROLL_PAUSE_TIME)
        self.driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight*(3/6));")
        time.sleep(SCROLL_PAUSE_TIME)
        self.driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight*(4/6));")
        time.sleep(SCROLL_PAUSE_TIME)
        self.driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight*(5/6));")
        time.sleep(SCROLL_PAUSE_TIME)
        self.driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight*(6/6));")
        time.sleep(1)


    def _create_product_item(self,response):
        # init container and page
        item = ProductItem()
        req = requests.get(response.url,self.headers)
        details_soup = bs(req.content, "html.parser")
        # fetch all features
        data = str(details_soup.find('script', id='linkStore',type='text/json'))
        script_len = len("</script>")
        js_text = data.split(">",1)[1][:-script_len]  #need to scrape off all non json characters
        pro = json.loads(js_text)
        try:
            sale_price = pro['page']['product']['currentSku']['salePrice']  # exist only if it is on sale
        except KeyError:
            sale_price = None
        try:
            # the following features must exist, otherwise it indicates that the href failed
            description = pro['page']['product']['content']['seoMetaDescription']
            product_name = pro['page']['product']['content']['seoTitle']
            brand_name = pro['page']['product']['productDetails']['brand']['displayName']
            original_category = pro['page']['product']['parentCategory']['displayName']
            rating = pro['page']['product']['productDetails']['rating']
            reviews = pro['page']['product']['productDetails']['reviews']
            skuId = pro['page']['product']['currentSku']['skuId']
            full_price = pro['page']['product']['currentSku']['listPrice']
            is_out_of_stock = pro['page']['product']['currentSku']['isOutOfStock']
            imagehref = pro['page']['product']['currentSku']['skuImages']['imageUrl']
            href = pro['page']['product']['currentSku']['targetUrl']
            few_left = pro['page']['product']['currentSku']['isOnlyFewLeft']
        except KeyError as e:
            LOG.info(f'Cannot handle {response.url} normally, has been ignored')
            return

        # feed container with collected features and parse
        item['productID'] = skuId if skuId else None
        item['store'] = STORE_NAME
        item['main_category'] = 'beauty' # most items are makeup or something similar to that
        item['original_category'] = original_category if original_category else None
        item['brand'] = brand_name if brand_name else None
        item['name'] = product_name if product_name else None
        item['href'] = response.url if response.url else None
        item['imagehref'] = (self.base_url + imagehref) if imagehref else None  # change the pic size of upload version
        item['rating'] = rating if rating else None
        item['full_price'] = float(full_price.replace('$','')) if full_price else None
        item['price'] = float(sale_price.replace('$','')) if sale_price else item['full_price']
        item['description'] = description if description else None
        item['num_reviews'] = reviews if reviews else 0

        # get in_stock and stock_level
        if is_out_of_stock:
            item['in_stock'] = 0
            item["stock_level"] = "unavailable"
        else:
            item['in_stock'] = 1
            item["stock_level"] = "available"
        if few_left:
            item["stock_level"] = "last_few_items"

        if _useful_item(item):
            yield item
        else:
            LOG.info("Skipped low quality product: {}".format(
                item['productID']))

def _useful_item(product):
    # filter those items in relative low quality
    return "rating" in product and product['rating'] is not None and product[
        "rating"] >= 4 and "num_reviews" in product and product[
            'num_reviews'] is not None and product["num_reviews"] >= 50

class SephoraInDBSpider(SephoraFullSpider, BaseInDBSpider):
    """
    To run the spider, use the command below
    Command:
    
    screapy crawl sephora_in_db_spider
    
    """
    name = 'sephora_in_db_spider'
    allowed_domains = ["www.sephora.com"]

    def __init__(self, *a, **kw):
        super().__init__(*a, store_name=STORE_NAME, **kw)

    def start_requests(self):
        for url in self.url_list:
            yield scrapy.Request(url=url,
                                callback=self._create_product_item,
                                meta={
                                    'handle_httpstatus_list': [302],
                                })

    def convert_item_to_url(self, item: Dict):
        return item["href"]
