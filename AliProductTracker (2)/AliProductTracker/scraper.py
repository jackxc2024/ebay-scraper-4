import requests
from bs4 import BeautifulSoup
import time
import random
import logging
import re
from urllib.parse import urljoin, quote
from app import db
from models import ScrapingJob, Product
from datetime import datetime

class ProductScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        })
        self.base_url = 'https://www.ebay.com'  # Switch to eBay which is more scraper-friendly
        self.min_delay = 2  # Respectful delay
        self.max_delay = 4  # Respectful delay
        
    def _delay(self):
        """Add random delay between requests to avoid being blocked"""
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)
        
    def _clean_price(self, price_text):
        """Clean and extract price from text"""
        if not price_text:
            return None
        # Remove currency symbols and extra whitespace
        price = re.sub(r'[^\d.,]', '', price_text.strip())
        return price if price else None
        
    def _clean_rating(self, rating_text):
        """Extract rating as float"""
        if not rating_text:
            return None
        try:
            rating = re.search(r'(\d+\.?\d*)', rating_text)
            return float(rating.group(1)) if rating else None
        except:
            return None
            
    def _clean_review_count(self, review_text):
        """Extract review count as integer"""
        if not review_text:
            return None
        try:
            # Look for numbers in parentheses or standalone
            review_count = re.search(r'(\d+)', review_text.replace(',', ''))
            return int(review_count.group(1)) if review_count else None
        except:
            return None
    
    def search_products(self, search_term, max_pages=3, job_id=None):
        """
        Search for products on AliExpress
        """
        try:
            job = ScrapingJob.query.get(job_id) if job_id else None
            if job:
                job.status = 'running'
                job.total_pages = max_pages
                db.session.commit()
            
            all_products = []
            
            for page in range(1, max_pages + 1):
                logging.info(f"Scraping page {page} for search term: {search_term}")
                
                if job:
                    job.current_page = page
                    db.session.commit()
                
                # Construct eBay search URL
                search_url = f"{self.base_url}/sch/i.html"
                params = {
                    '_nkw': search_term,
                    '_pgn': page,
                    '_ipg': 60  # Items per page
                }
                
                try:
                    response = self.session.get(search_url, params=params, timeout=30)
                    response.raise_for_status()
                    
                    # Save HTML for debugging (only for first page)
                    if page == 1:
                        with open(f'debug_page_{search_term.replace(" ", "_")}.html', 'w', encoding='utf-8') as f:
                            f.write(response.text)
                        logging.info(f"Saved HTML content to debug_page_{search_term.replace(' ', '_')}.html")
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    products = self._parse_product_listing(soup, job_id)
                    
                    if not products:
                        logging.warning(f"No products found on page {page}")
                        break
                        
                    all_products.extend(products)
                    logging.info(f"Found {len(products)} products on page {page}")
                    
                    # Add delay between page requests
                    if page < max_pages:
                        self._delay()
                        
                except requests.RequestException as e:
                    logging.error(f"Error scraping page {page}: {str(e)}")
                    if job:
                        job.error_message = f"Error on page {page}: {str(e)}"
                        db.session.commit()
                    continue
            
            if job:
                job.status = 'completed'
                job.completed_at = datetime.utcnow()
                db.session.commit()
                
            logging.info(f"Scraping completed. Total products found: {len(all_products)}")
            return all_products
            
        except Exception as e:
            logging.error(f"Error in search_products: {str(e)}")
            if job:
                job.status = 'failed'
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                db.session.commit()
            raise
    
    def _parse_product_listing(self, soup, job_id=None):
        """
        Parse product information from search results page
        """
        products = []
        
        # eBay product selectors
        product_selectors = [
            'div.s-item',
            'div[data-viewport]',
            'div.srp-results div.s-item',
            'li.s-item',
            'div.s-item__wrapper',
            'div[class*="item"]'
        ]
        
        product_elements = []
        for selector in product_selectors:
            product_elements = soup.select(selector)
            if product_elements:
                logging.info(f"Found {len(product_elements)} products using selector: {selector}")
                break
        
        if not product_elements:
            # Fallback: look for any div with product-like attributes
            product_elements = soup.find_all('div', attrs={'data-product-id': True})
            if not product_elements:
                # Debug: log the page structure to understand what we're getting
                logging.warning("No product elements found with any selector")
                logging.debug(f"Page title: {soup.title.string if soup.title else 'No title'}")
                logging.debug(f"Page contains {len(soup.find_all('div'))} div elements")
                
                # Try to find any elements that might contain product information
                possible_products = soup.find_all(attrs={'class': lambda x: x and any(term in str(x).lower() for term in ['product', 'item', 'card', 'result'])})
                logging.debug(f"Found {len(possible_products)} elements with product-related classes")
                
                if len(possible_products) > 0:
                    logging.debug(f"Sample element classes: {possible_products[0].get('class') if possible_products[0].get('class') else 'No class'}")
                
                return products
        
        for element in product_elements[:20]:  # Limit to 20 products per page
            try:
                product_data = self._extract_product_data(element)
                if product_data and product_data.get('title'):
                    
                    # Save to database if job_id provided
                    if job_id:
                        product = Product(
                            job_id=job_id,
                            title=product_data.get('title', ''),
                            price=product_data.get('price'),
                            original_price=product_data.get('original_price'),
                            rating=product_data.get('rating'),
                            review_count=product_data.get('review_count'),
                            seller_name=product_data.get('seller_name'),
                            product_url=product_data.get('product_url'),
                            image_url=product_data.get('image_url'),
                            shipping_info=product_data.get('shipping_info'),
                            discount_percentage=product_data.get('discount_percentage')
                        )
                        db.session.add(product)
                    
                    products.append(product_data)
                    
            except Exception as e:
                logging.error(f"Error parsing product element: {str(e)}")
                continue
        
        if job_id:
            db.session.commit()
            
        return products
    
    def _extract_product_data(self, element):
        """
        Extract product data from a product element
        """
        product = {}
        
        try:
            # Title - eBay specific selectors
            title_selectors = [
                'h3.s-item__title',
                'a[role="link"] span',
                'h3 a',
                '.s-item__title',
                'a[title]'
            ]
            title = None
            for selector in title_selectors:
                title_elem = element.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True) or title_elem.get('title')
                    if title and len(title) > 5:
                        # Clean eBay-specific prefixes
                        title = title.replace('New Listing', '').strip()
                        break
            
            if not title:
                return None
                
            product['title'] = title[:500]  # Limit title length
            
            # Price - eBay specific selectors
            price_selectors = [
                '.s-item__price .notranslate',
                '.s-item__price',
                '.notranslate',
                '[class*="price"]'
            ]
            for selector in price_selectors:
                price_elem = element.select_one(selector)
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    product['price'] = self._clean_price(price_text)
                    break
            
            # Original price (for discount calculation)
            original_price_selectors = [
                '.price-original', '.original-price', '[class*="original"]'
            ]
            for selector in original_price_selectors:
                orig_price_elem = element.select_one(selector)
                if orig_price_elem:
                    orig_price_text = orig_price_elem.get_text(strip=True)
                    product['original_price'] = self._clean_price(orig_price_text)
                    break
            
            # Rating
            rating_selectors = [
                '[class*="rating"]', '[class*="star"]', '.rate'
            ]
            for selector in rating_selectors:
                rating_elem = element.select_one(selector)
                if rating_elem:
                    rating_text = rating_elem.get_text(strip=True)
                    product['rating'] = self._clean_rating(rating_text)
                    break
            
            # Review count
            review_selectors = [
                '[class*="review"]', '[class*="feedback"]', '[class*="order"]'
            ]
            for selector in review_selectors:
                review_elem = element.select_one(selector)
                if review_elem:
                    review_text = review_elem.get_text(strip=True)
                    product['review_count'] = self._clean_review_count(review_text)
                    break
            
            # Product URL
            link_elem = element.select_one('a[href]')
            if link_elem:
                href = link_elem.get('href')
                if href:
                    if href.startswith('//'):
                        product['product_url'] = 'https:' + href
                    elif href.startswith('/'):
                        product['product_url'] = self.base_url + href
                    elif href.startswith('http'):
                        product['product_url'] = href
            
            # Image URL
            img_elem = element.select_one('img[src], img[data-src]')
            if img_elem:
                img_src = img_elem.get('src') or img_elem.get('data-src')
                if img_src:
                    if img_src.startswith('//'):
                        product['image_url'] = 'https:' + img_src
                    elif img_src.startswith('/'):
                        product['image_url'] = self.base_url + img_src
                    elif img_src.startswith('http'):
                        product['image_url'] = img_src
            
            # Seller name
            seller_selectors = [
                '[class*="seller"]', '[class*="store"]', '[class*="shop"]'
            ]
            for selector in seller_selectors:
                seller_elem = element.select_one(selector)
                if seller_elem:
                    seller_text = seller_elem.get_text(strip=True)
                    if seller_text and len(seller_text) > 2:
                        product['seller_name'] = seller_text[:200]
                        break
            
            # Shipping info
            shipping_selectors = [
                '[class*="shipping"]', '[class*="delivery"]', '[class*="freight"]'
            ]
            for selector in shipping_selectors:
                shipping_elem = element.select_one(selector)
                if shipping_elem:
                    shipping_text = shipping_elem.get_text(strip=True)
                    if shipping_text:
                        product['shipping_info'] = shipping_text[:200]
                        break
            
            return product
            
        except Exception as e:
            logging.error(f"Error extracting product data: {str(e)}")
            return None
