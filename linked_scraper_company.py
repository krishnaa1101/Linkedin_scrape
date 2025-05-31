import time
import gspread
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from deep_translator import GoogleTranslator
from google.oauth2.service_account import Credentials
import random
import re
from urllib.parse import urljoin, urlparse

class LinkedInCompanyExtractor:
    def _init_(self, email, password, credentials_path, sheet_name):
        """
        Initialize the LinkedIn extractor
        
        :param email: LinkedIn email
        :param password: LinkedIn password
        :param credentials_path: Path to Google Service Account JSON file
        :param sheet_name: Name of the Google Sheet to write data to
        """
        self.email = email
        self.password = password
        self.driver = None
        self.translator = GoogleTranslator(source='auto', target='en')
        self.wait = None
        
        # Setup Google Sheets connection
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        
        creds = Credentials.from_service_account_file(credentials_path, scopes=scope)
        self.gc = gspread.authorize(creds)
        self.sheet = self.gc.open(sheet_name).sheet1
        
        # Keywords for finding founders and engineering heads
        self.founder_keywords = ['CEO', 'CTO', 'Founder', 'Co-Founder', 'Chief Executive', 'Chief Technology']
        self.engineering_keywords = ['Tech Lead', 'Engineering Manager', 'Director of Engineering', 
                                   'Engineering Lead', 'VP Engineering', 'Head of Engineering',
                                   'Senior Engineering Manager', 'Principal Engineer', 'Staff Engineer']
        
        # Setup headers - handle existing sheet with issues
        try:
            # Try to get existing records
            existing_records = self.sheet.get_all_records()
            if not existing_records:
                # Sheet is empty, add headers
                headers = ['Company Name', 'Description/Overview', 'Job Posts', 
                          'Number of Employees', 'Industry', 'Location', 'Website', 
                          'Domain URL', 'Phone Number', 'Email Contact', 'Company URL',
                          'Founders', 'Engineering Heads']
                self.sheet.insert_row(headers, 1)
                print("Added headers to empty sheet")
        except Exception as e:
            # If there's an issue with existing headers, clear and recreate
            print(f"Issue with existing headers: {e}")
            print("Clearing sheet and adding fresh headers...")
            
            # Clear the entire sheet
            self.sheet.clear()
            
            # Add fresh headers
            headers = ['Company Name', 'Description/Overview', 'Job Posts', 
                      'Number of Employees', 'Industry', 'Location', 'Website',
                      'Domain URL', 'Phone Number', 'Email Contact', 'Company URL',
                      'Founders', 'Engineering Heads']
            self.sheet.insert_row(headers, 1)
            print("Sheet cleared and fresh headers added")
    
    def setup_driver(self):
        """Setup Chrome WebDriver with LinkedIn-friendly options"""
        options = webdriver.ChromeOptions()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--disable-extensions")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        # Add these for better stability
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.wait = WebDriverWait(self.driver, 20)  # Increased timeout
    
    def login_to_linkedin(self):
        """Login to LinkedIn"""
        try:
            print("Logging into LinkedIn...")
            self.driver.get("https://www.linkedin.com/login")
            time.sleep(3)
            
            # Enter email
            email_field = self.wait.until(EC.presence_of_element_located((By.ID, "username")))
            email_field.clear()
            email_field.send_keys(self.email)
            
            # Enter password
            password_field = self.driver.find_element(By.ID, "password")
            password_field.clear()
            password_field.send_keys(self.password)
            
            # Click login button using safe_click method
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            if not self.safe_click(login_button):
                print("Failed to click login button")
                return False
            
            # Wait for login to complete
            time.sleep(8)  # Increased wait time
            
            # Check if we're logged in successfully
            current_url = self.driver.current_url.lower()
            if any(keyword in current_url for keyword in ["feed", "mynetwork", "in/", "home"]):
                print("Successfully logged into LinkedIn!")
                return True
            else:
                print(f"Login may have failed. Current URL: {self.driver.current_url}")
                return False
                
        except Exception as e:
            print(f"Login error: {e}")
            return False
    
    def safe_click(self, element):
        """
        Safely click an element with multiple fallback methods
        """
        try:
            # Method 1: Standard click
            element.click()
            return True
        except Exception as e1:
            try:
                # Method 2: JavaScript click
                self.driver.execute_script("arguments[0].click();", element)
                return True
            except Exception as e2:
                try:
                    # Method 3: Action chains click
                    from selenium.webdriver.common.action_chains import ActionChains
                    ActionChains(self.driver).click(element).perform()
                    return True
                except Exception as e3:
                    print(f"All click methods failed: {e1}, {e2}, {e3}")
                    return False

    def detect_and_translate(self, text):
        """
        Translate text to English if needed
        """
        if not text or len(text.strip()) < 3:
            return text
        
        try:
            # Try to translate - GoogleTranslator will auto-detect language
            translated = self.translator.translate(text)
            return translated if translated else text
        except Exception as e:
            print(f"Translation error: {e}")
            return text
    
    def wait_for_page_load(self):
        """Wait for page to fully load"""
        try:
            # Wait for body to be present
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            # Additional wait for dynamic content
            time.sleep(random.uniform(3, 5))
        except TimeoutException:
            print("Page load timeout")
    
    def find_element_with_selectors(self, selectors, return_text=True):
        """Try multiple selectors to find an element"""
        for selector in selectors:
            try:
                if return_text:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    text = element.text.strip()
                    if text:
                        return text
                else:
                    return self.driver.find_element(By.CSS_SELECTOR, selector)
            except NoSuchElementException:
                continue
        return None
    
    def extract_domain_from_url(self, url):
        """Extract domain from URL"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return ""
    
    def extract_contact_info(self, data):
        """Extract phone number and email from page source"""
        try:
            page_source = self.driver.page_source
            
            # Email patterns
            email_patterns = [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                r'mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})'
            ]
            
            # Phone patterns (international formats)
            phone_patterns = [
                r'\+\d{1,3}[\s-]?\d{1,4}[\s-]?\d{1,4}[\s-]?\d{1,9}',
                r'\(\d{3}\)\s?\d{3}[-.]?\d{4}',
                r'\d{3}[-.]?\d{3}[-.]?\d{4}',
                r'\+\d{1,3}\s?\d{3,4}\s?\d{3,4}\s?\d{3,4}'
            ]
            
            emails = []
            phones = []
            
            # Extract emails
            for pattern in email_patterns:
                matches = re.findall(pattern, page_source, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0] if match else ""
                    if match and '@' in match and '.' in match:
                        # Filter out common non-contact emails
                        if not any(skip in match.lower() for skip in ['noreply', 'no-reply', 'support', 'help', 'info@linkedin']):
                            emails.append(match)
            
            # Extract phone numbers
            for pattern in phone_patterns:
                matches = re.findall(pattern, page_source)
                for match in matches:
                    # Clean and validate phone number
                    clean_phone = re.sub(r'[^\d+()-]', '', match)
                    if len(clean_phone) >= 10:
                        phones.append(match)
            
            # Remove duplicates and get first few
            data['email_contact'] = "; ".join(list(set(emails))[:3]) if emails else "Not found"
            data['phone_number'] = "; ".join(list(set(phones))[:2]) if phones else "Not found"
            
        except Exception as e:
            print(f"Error extracting contact info: {e}")
            data['email_contact'] = "Error extracting"
            data['phone_number'] = "Error extracting"
    
    def search_people_by_keyword(self, company_url, keywords, role_type="people"):
        """Search for people in company by keywords"""
        people_found = []
        
        try:
            # Extract company identifier from URL
            company_id = company_url.rstrip('/').split('/')[-1]
            base_company_url = company_url.rstrip('/')
            
            for keyword in keywords:
                try:
                    print(f"  Searching for {role_type} with keyword: {keyword}")
                    
                    # Construct people search URL
                    people_url = f"{base_company_url}/people/?keywords={keyword.replace(' ', '%20')}"
                    
                    self.driver.get(people_url)
                    self.wait_for_page_load()
                    
                    # Scroll to load more people
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                    time.sleep(3)
                    
                    # Find people cards with various selectors
                    people_selectors = [
                        ".org-people-profile-card",
                        ".artdeco-entity-lockup",
                        "[data-test-id='people-card']",
                        ".org-people-profile-card__profile-info",
                        ".artdeco-entity-lockup__content"
                    ]
                    
                    found_people = []
                    
                    for selector in people_selectors:
                        try:
                            people_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            print(f"    Found {len(people_elements)} elements with selector: {selector}")
                            
                            for person_elem in people_elements[:5]:  # Limit to first 5 per keyword
                                try:
                                    person_info = self.extract_person_info(person_elem, keyword)
                                    if person_info and person_info not in found_people:
                                        found_people.append(person_info)
                                        print(f"    Found: {person_info}")
                                except Exception as e:
                                    print(f"    Error extracting person info: {e}")
                                    continue
                            
                            if found_people:
                                people_found.extend(found_people)
                                break  # Stop trying other selectors if we found people
                                
                        except Exception as e:
                            print(f"    Error with selector {selector}: {e}")
                            continue
                    
                    # Random delay between keyword searches
                    time.sleep(random.uniform(2, 4))
                    
                except Exception as e:
                    print(f"  Error searching for {keyword}: {e}")
                    continue
        
        except Exception as e:
            print(f"Error in people search: {e}")
        
        return people_found[:10]  # Return max 10 people
    
    def extract_person_info(self, person_element, search_keyword):
        """Extract name, title, and LinkedIn URL from person element"""
        try:
            # Try to find name
            name_selectors = [
                ".artdeco-entity-lockup__title a",
                ".org-people-profile-card__profile-title a",
                "a[data-test-id='people-card-name']",
                ".artdeco-entity-lockup__title",
                "h3 a",
                ".profile-link"
            ]
            
            name = ""
            linkedin_url = ""
            
            # Extract name and URL
            for selector in name_selectors:
                try:
                    name_elem = person_element.find_element(By.CSS_SELECTOR, selector)
                    if name_elem.text.strip():
                        name = name_elem.text.strip()
                        if name_elem.tag_name.lower() == 'a':
                            linkedin_url = name_elem.get_attribute('href')
                        break
                except:
                    continue
            
            # Try to find title/position
            title_selectors = [
                ".artdeco-entity-lockup__subtitle",
                ".org-people-profile-card__profile-subtitle",
                "[data-test-id='people-card-subtitle']",
                ".artdeco-entity-lockup__content .t-14",
                ".profile-subtitle"
            ]
            
            title = ""
            for selector in title_selectors:
                try:
                    title_elem = person_element.find_element(By.CSS_SELECTOR, selector)
                    if title_elem.text.strip():
                        title = title_elem.text.strip()
                        break
                except:
                    continue
            
            # Validate that this person matches the search keyword
            full_text = f"{name} {title}".lower()
            if not any(keyword.lower() in full_text for keyword in [search_keyword]):
                return None
            
            if name:
                return {
                    'name': name,
                    'title': title or search_keyword,
                    'linkedin_url': linkedin_url or "URL not found"
                }
            
        except Exception as e:
            print(f"Error extracting person info: {e}")
        
        return None
    
    def extract_company_data(self, company_url):
        """
        Extract company data from LinkedIn company page
        """
        data = {
            'company_name': '',
            'description': '',
            'job_posts': '',
            'employees': '',
            'industry': '',
            'location': '',
            'website': '',
            'domain_url': '',
            'phone_number': '',
            'email_contact': '',
            'url': company_url,
            'founders': '',
            'engineering_heads': ''
        }
        
        try:
            print(f"Extracting data from: {company_url}")
            
            # Try main company page first
            main_url = company_url.replace('/life/', '/').replace('/life', '/')
            if not main_url.endswith('/'):
                main_url += '/'
            
            self.driver.get(main_url)
            self.wait_for_page_load()
            
            # Scroll to load dynamic content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(2)
            
            # Extract company name with more comprehensive selectors
            name_selectors = [
                "h1.org-top-card-summary__title",
                ".org-top-card-summary__title",
                "h1.organization-outlet__name",
                ".organization-outlet__name",
                "h1[data-test-id='org-name']",
                ".org-top-card-summary-info-list__info-item h1",
                ".pv-text-details__company-name",
                "h1",
                ".t-24.t-black.t-normal"
            ]
            
            company_name = self.find_element_with_selectors(name_selectors)
            if company_name:
                data['company_name'] = company_name
                print(f"Found company name: {company_name}")
            
            # Extract contact information from main page
            self.extract_contact_info(data)
            
            # Try to extract basic info from main page first
            self.extract_from_main_page(data)
            
            # Navigate to About section for more details
            about_url = main_url + 'about/'
            print(f"Navigating to about page: {about_url}")
            self.driver.get(about_url)
            self.wait_for_page_load()
            
            # Scroll to load all content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)
            
            # Extract description/overview with updated selectors
            if not data['description']:
                desc_selectors = [
                    ".org-about-company-module__company-description p",
                    ".break-words p",
                    ".org-about-us-organization-description__text",
                    ".break-words",
                    ".org-page-details__definition-text",
                    "[data-test-id='about-us__description']",
                    ".organization-about__text",
                    ".org-about-company-module p",
                    ".artdeco-card p",
                    ".section-info p"
                ]
                
                description_parts = []
                for selector in desc_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for elem in elements:
                            text = elem.text.strip()
                            if text and len(text) > 30 and text not in description_parts:
                                description_parts.append(text)
                                if len(description_parts) >= 2:  # Limit to avoid too much text
                                    break
                        if description_parts:
                            break
                    except:
                        continue
                
                if description_parts:
                    full_description = " ".join(description_parts)
                    data['description'] = self.detect_and_translate(full_description)
                    print(f"Found description: {data['description'][:100]}...")
            
            # Enhanced extraction for company details
            self.extract_company_details(data)
            
            # Extract website and domain
            if data['website']:
                data['domain_url'] = self.extract_domain_from_url(data['website'])
            
            # Navigate to Jobs section with better error handling
            self.extract_job_posts(data, main_url)
            
            # Extract founders and engineering heads
            print("Searching for founders...")
            founders = self.search_people_by_keyword(main_url, self.founder_keywords, "founders")
            if founders:
                founder_list = []
                for founder in founders:
                    founder_str = f"{founder['name']} ({founder['title']}) - {founder['linkedin_url']}"
                    founder_list.append(founder_str)
                data['founders'] = "; ".join(founder_list)
                print(f"Found {len(founders)} founders")
            else:
                data['founders'] = "No founders found"
            
            print("Searching for engineering heads...")
            eng_heads = self.search_people_by_keyword(main_url, self.engineering_keywords, "engineering heads")
            if eng_heads:
                eng_list = []
                for eng in eng_heads:
                    eng_str = f"{eng['name']} ({eng['title']}) - {eng['linkedin_url']}"
                    eng_list.append(eng_str)
                data['engineering_heads'] = "; ".join(eng_list)
                print(f"Found {len(eng_heads)} engineering heads")
            else:
                data['engineering_heads'] = "No engineering heads found"
            
            return data
            
        except Exception as e:
            print(f"Error extracting data from {company_url}: {e}")
            data['description'] = f"Error: {str(e)}"
            return data
    
    def extract_from_main_page(self, data):
        """Extract basic info from main company page"""
        try:
            # Look for employee count on main page
            main_page_text = self.driver.page_source
            
            # Patterns for employee count
            patterns = [
                r'(\d{1,3}(?:,\d{3})(?:-\d{1,3}(?:,\d{3}))?)\s*employees?',
                r'(\d{1,3}(?:,\d{3})*)\s*followers',
                r'Size:\s*(\d{1,3}(?:,\d{3})(?:-\d{1,3}(?:,\d{3}))?)',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, main_page_text, re.IGNORECASE)
                if matches:
                    data['employees'] = matches[0] + " employees"
                    print(f"Found employee count from main page: {data['employees']}")
                    break
            
            # Look for website URLs
            website_patterns = [
                r'https?://(?:www\.)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s]*)?',
                r'"website":"(https?://[^"]+)"'
            ]
            
            for pattern in website_patterns:
                matches = re.findall(pattern, main_page_text)
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0] if match else ""
                    if match and 'linkedin.com' not in match.lower() and not data['website']:
                        data['website'] = match if match.startswith('http') else f"https://{match}"
                        print(f"Found website: {data['website']}")
                        break
                if data['website']:
                    break
            
            # Look for industry hints
            industry_keywords = ['Technology', 'Software', 'Consulting', 'Healthcare', 'Finance', 
                               'Education', 'Manufacturing', 'Retail', 'Real Estate', 'Media']
            for keyword in industry_keywords:
                if keyword.lower() in main_page_text.lower() and not data['industry']:
                    data['industry'] = keyword
                    print(f"Found industry hint: {keyword}")
                    break
                    
        except Exception as e:
            print(f"Error extracting from main page: {e}")
    
    def extract_company_details(self, data):
        """Extract detailed company information"""
        try:
            # More comprehensive selectors for different page layouts
            detail_sections = [
                ".org-page-details__definition-text",
                ".org-about-company-module__company-details dd",
                ".org-about-us-company-module__company-details dd",
                ".artdeco-card dd",
                ".section-info dd"
            ]
            
            all_details = []
            for selector in detail_sections:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        text = elem.text.strip()
                        if text and text not in all_details:
                            all_details.append(text)
                except:
                    continue
            
            # Process collected details
            for detail in all_details:
                detail_lower = detail.lower()
                
                # Industry detection
                if not data['industry'] and len(detail.split()) <= 8:
                    # Skip if it looks like a location or employee count
                    if not any(word in detail_lower for word in ['employees', 'people', 'city', 'country', 'street', 'avenue']):
                        data['industry'] = detail
                        print(f"Found industry: {detail}")
                
                # Location detection
                if not data['location']:
                    location_indicators = ['headquarters', 'hq', 'located', 'based', 'city', 'country']
                    if any(indicator in detail_lower for indicator in location_indicators):
                        data['location'] = detail
                        print(f"Found location: {detail}")
                
                # Employee count if not found yet
                if not data['employees'] and any(word in detail_lower for word in ['employee', 'people', 'staff', 'team size']):
                    data['employees'] = detail
                    print(f"Found employee info: {detail}")
                
                # Website detection
                if not data['website'] and ('http' in detail or '.com' in detail or '.org' in detail):
                    if 'linkedin.com' not in detail.lower():
                        data['website'] = detail
                        print(f"Found website: {detail}")
            
            # Try XPath for more specific targeting
            try:
                # Look for specific patterns in the about page
                xpath_selectors = [
                    "//dt[contains(text(), 'Industry')]/following-sibling::dd",
                    "//dt[contains(text(), 'Company size')]/following-sibling::dd",
                    "//dt[contains(text(), 'Headquarters')]/following-sibling::dd",
                    "//dt[contains(text(), 'Founded')]/following-sibling::dd",
                    "//dt[contains(text(), 'Website')]/following-sibling::dd"
                ]
                
                for xpath in xpath_selectors:
                    try:
                        element = self.driver.find_element(By.XPATH, xpath)
                        text = element.text.strip()
                        
                        if 'Industry' in xpath and not data['industry']:
                            data['industry'] = text
                            print(f"Found industry via XPath: {text}")
                        elif 'size' in xpath and not data['employees']:
                            data['employees'] = text
                            print(f"Found company size via XPath: {text}")
                        elif 'Headquarters' in xpath and not data['location']:
                            data['location'] = text
                            print(f"Found location via XPath: {text}")
                        elif 'Website' in xpath and not data['website']:
                            data['website'] = text
                            print(f"Found website via XPath: {text}")
                    except:
                        continue
                        
            except Exception as e:
                print(f"XPath extraction error: {e}")
                
        except Exception as e:
            print(f"Error extracting company details: {e}")
    
    def extract_job_posts(self, data, main_url):
        """Extract job postings with improved selectors"""
        try:
            jobs_url = main_url + 'jobs/'
            print(f"Navigating to jobs page: {jobs_url}")
            self.driver.get(jobs_url)
            self.wait_for_page_load()
            
            # Scroll to load jobs
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(3)
            
            job_titles = []
            
            # Updated job selectors for 2025
            job_selectors = [
                ".job-card-list__title a",
                ".job-card-container__link",
                ".job-card-container__primary-description",
                "a[data-tracking-control-name*='job']",
                ".job-card-container .job-card-list__title",
                "[data-test-id='job-title']",
                ".jobs-search-results-list .job-card-container__link",
                ".artdeco-entity-lockup__title a",
                ".job-card-container .artdeco-entity-lockup__title"
            ]
            
            # Try each selector
            for selector in job_selectors:
                try:
                    job_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    print(f"Found {len(job_elements)} elements with selector: {selector}")
                    
                    if job_elements:
                        for job_elem in job_elements[:10]:  # Limit to first 10
                            try:
                                # Try different methods to get job title
                                job_title = ""
                                
                                # Method 1: Direct text
                                if job_elem.text.strip():
                                    job_title = job_elem.text.strip()
                                
                                # Method 2: Get attribute if it's a link
                                elif job_elem.tag_name == 'a':
                                    job_title = job_elem.get_attribute('aria-label') or job_elem.get_attribute('title')
                                
                                # Method 3: Look for nested elements
                                if not job_title:
                                    nested = job_elem.find_elements(By.CSS_SELECTOR, "*")
                                    for nest in nested:
                                        if nest.text.strip():
                                            job_title = nest.text.strip()
                                            break
                                
                                # Clean and validate job title
                                if job_title and len(job_title) > 3 and len(job_title) < 100:
                                    # Remove common unwanted text
                                    job_title = job_title.replace('Apply now', '').strip()
                                    if job_title and job_title not in job_titles:
                                        job_titles.append(job_title)
                                        print(f"Found job: {job_title}")
                                        
                            except Exception as e:
                                print(f"Error processing job element: {e}")
                                continue
                        
                        if job_titles:
                            break  # If we found jobs with this selector, stop trying others
                            
                except Exception as e:
                    print(f"Error with job selector {selector}: {e}")
                    continue
            
            # Final attempt: search page source for job patterns
            if not job_titles:
                try:
                    page_source = self.driver.page_source
                    
                    # Look for common job title patterns
                    job_patterns = [
                        r'"jobTitle":"([^"]+)"',
                        r'aria-label="([^"](?:engineer|developer|manager|analyst|specialist|coordinator|assistant|director|lead|senior|junior)[^"])"',
                    ]
                    
                    for pattern in job_patterns:
                        matches = re.findall(pattern, page_source, re.IGNORECASE)
                        for match in matches[:5]:
                            if match and len(match) > 3 and match not in job_titles:
                                job_titles.append(match)
                                
                except Exception as e:
                    print(f"Error with regex job extraction: {e}")
            
            if job_titles:
                data['job_posts'] = "; ".join(job_titles[:5])
                print(f"Successfully found {len(job_titles)} job posts")
            else:
                data['job_posts'] = "No current job openings found"
                print("No job posts found")
                
        except Exception as e:
            print(f"Error extracting job posts: {e}")
            data['job_posts'] = "Error extracting jobs"
    
    def process_companies(self, company_urls):
        """
        Process multiple LinkedIn company URLs
        """
        self.setup_driver()
        
        try:
            # Login to LinkedIn
            if not self.login_to_linkedin():
                print("Failed to login to LinkedIn. Exiting...")
                return
            
            # Wait a bit after login
            time.sleep(5)
            
            for i, url in enumerate(company_urls):
                print(f"\n{'='*50}")
                print(f"Processing company {i+1}/{len(company_urls)}")
                print(f"URL: {url}")
                print(f"{'='*50}")
                
                # Extract data
                company_data = self.extract_company_data(url)
                
                # Print extracted data for debugging
                print(f"Extracted data:")
                for key, value in company_data.items():
                    print(f"  {key}: {value}")
                
                # Prepare row data with fallbacks
                row_data = [
                    company_data['company_name'] or "Company name not found",
                    company_data['description'] or "Description not available", 
                    company_data['job_posts'] or "Job information not available",
                    company_data['employees'] or "Employee count not available",
                    company_data['industry'] or "Industry not specified",
                    company_data['location'] or "Location not available",
                    company_data['website'] or "Website not found",
                    company_data['domain_url'] or "Domain not found",
                    company_data['phone_number'] or "Phone not found",
                    company_data['email_contact'] or "Email not found",
                    company_data['url'],
                    company_data['founders'] or "Founders not found",
                    company_data['engineering_heads'] or "Engineering heads not found"
                ]
                
                # Add to Google Sheet
                try:
                    self.sheet.append_row(row_data)
                    print(f"✅ Added data for: {company_data['company_name'] or 'Unknown Company'}")
                except Exception as e:
                    print(f"❌ Error adding to sheet: {e}")
                
                # Random delay between requests (important for avoiding blocks)
                delay = random.uniform(10, 18)  # Increased delay for people searches
                print(f"Waiting {delay:.1f} seconds before next company...")
                time.sleep(delay)
                
        except Exception as e:
            print(f"Error during processing: {e}")
        finally:
            if self.driver:
                self.driver.quit()

# Main execution
def main():
    # Your configuration
    LINKEDIN_EMAIL = "hbagotia2005@gmail.com"
    LINKEDIN_PASSWORD = "Fl6kW!RH2!a535y"
    GOOGLE_CREDS_JSON = "google_sheets_credentials.json"
    GOOGLE_SHEET_NAME = "company details 2"
    
    LINKEDIN_COMPANY_URLS = [
        'https://www.linkedin.com/company/instaffo-gmbh/',
        'https://www.linkedin.com/company/accountone-gmbh/',
        'https://www.linkedin.com/company/usebraintrust/',
        'https://www.linkedin.com/company/optimus-search/',
        'https://www.linkedin.com/company/tietalent/',
    ]
    
    print("Starting LinkedIn Company Data Extraction...")
    print(f"Total companies to process: {len(LINKEDIN_COMPANY_URLS)}")
    print("New features: Founders, Engineering Heads, Contact Info, Domain URLs")
    
    # Initialize and run extractor
    extractor = LinkedInCompanyExtractor(
        LINKEDIN_EMAIL, 
        LINKEDIN_PASSWORD, 
        GOOGLE_CREDS_JSON, 
        GOOGLE_SHEET_NAME
    )
    
    # Process all companies
    extractor.process_companies(LINKEDIN_COMPANY_URLS)
    
    print("\n✅ Extraction completed! Check your Google Sheet for results.")
    print("Data extracted includes:")
    print("- Company basic info (name, description, employees, industry, location)")
    print("- Job postings")
    print("- Contact information (phone, email)")
    print("- Website and domain URL")
    print("- Founders (CEO, CTO, Co-Founders)")
    print("- Engineering Heads (Tech Leads, Engineering Managers, Directors)")

if _name_ == "_main_":
    main()