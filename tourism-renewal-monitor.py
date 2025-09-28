import pandas as pd
from playwright.sync_api import sync_playwright
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from datetime import datetime
import json
import os
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tourism_renewal_calendar.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TourismRenewalMonitor:
    def __init__(self, config_file="config.json"):
        self.base_url = "https://visa-fr-dz.capago.eu/rendezvous_annaba/"
        self.config = self.load_config(config_file)
        self.results = []
        
    def load_config(self, config_file):
        """Load configuration from JSON file"""
        default_config = {
            "email": {
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "sender_email": "",
                "sender_password": "",
                "recipient_email": ""
            },
            "monitoring": {
                "check_interval": 300,  # 5 minutes
                "max_retries": 3
            },
            "telegram": {
                "bot_token": "",
                "chat_id": ""
            }
        }
        
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        else:
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=4)
            logger.info(f"Created default config file: {config_file}")
            
        return default_config

    def send_email_notification(self, subject, body):
        """Send email notification"""
        try:
            if not self.config['email']['sender_email']:
                return
                
            msg = MIMEMultipart()
            msg['From'] = self.config['email']['sender_email']
            msg['To'] = self.config['email']['recipient_email']
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(self.config['email']['smtp_server'], 
                                self.config['email']['smtp_port'])
            server.starttls()
            server.login(self.config['email']['sender_email'], 
                        self.config['email']['sender_password'])
            
            server.send_message(msg)
            server.quit()
            logger.info("Email notification sent successfully")
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")

    def send_telegram_notification(self, message):
        """Send Telegram notification"""
        try:
            bot_token = self.config['telegram']['bot_token']
            chat_id = self.config['telegram']['chat_id']
            
            if bot_token and chat_id:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                data = {"chat_id": chat_id, "text": message}
                response = requests.post(url, data=data)
                
                if response.status_code == 200:
                    logger.info("Telegram notification sent successfully")
                else:
                    logger.error(f"Failed to send Telegram: {response.text}")
        except Exception as e:
            logger.error(f"Telegram notification error: {e}")

    def navigate_to_renewal_calendar(self, page):
        """Navigate specifically to tourism renewal calendar"""
        try:
            # Step 1: Basic form
            logger.info("Step 1: Basic form")
            page.fill('input[name="nb_travellers"]', '1')
            page.click('label[for="cgv"]', force=True)
            page.click('label[for="area_Annaba"]', force=True)
            page.click('label[for="standard"]', force=True)
            page.wait_for_timeout(2000)
            
            # Next
            page.click('.next-step a:has-text("Suivant")', force=True)
            page.wait_for_timeout(5000)
            
            # Step 2: Fill basic applicant info
            logger.info("Step 2: Applicant info for renewal")
            page.fill('input[name="lastname_traveller_1"]', 'TestRenewal', force=True)
            page.fill('input[name="firstname_traveller_1"]', 'TestUser', force=True)
            page.fill('input[name="phone_traveller_1"]', '+213123456789', force=True)
            page.fill('input[name="email_traveller_1"]', 'test@renewal.com', force=True)
            page.fill('input[name="email_confirm_traveller_1"]', 'test@renewal.com', force=True)
            page.fill('input[name="number_passport_traveller_1"]', 'R123456', force=True)
            
            # Select tourism visa type
            logger.info("Selecting tourism visa type")
            page.evaluate('''
                const select = document.querySelector('select[name="type_visa_traveller_1"]');
                if (select) {
                    select.value = "013-1C5AE5"; // Tourism visa value
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                }
            ''')
            page.wait_for_timeout(3000)
            
            # Select Schengen 12+ if the dropdown appears
            logger.info("Selecting Schengen 12+")
            try:
                page.evaluate('''
                    const precision1 = document.querySelector('select[name="precision1_traveller_1"]');
                    if (precision1) {
                        // Make it visible first
                        const wrapper = precision1.closest('[data-input="precision1"]');
                        if (wrapper) wrapper.style.display = 'block';
                        
                        // Set value for Schengen 12+
                        precision1.value = "1";
                        precision1.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                ''')
                page.wait_for_timeout(2000)
            except Exception as e:
                logger.warning(f"Schengen selection issue: {e}")
            
            # CRITICAL: Select renewal category specifically
            logger.info("Selecting RENEWAL category")
            
            # Try multiple approaches to select renewal
            renewal_selected = False
            
            # Approach 1: Try dropdown selection with value "2" for renewal
            try:
                page.evaluate('''
                    const precision2 = document.querySelector('select[name="precision2_traveller_1"]');
                    if (precision2) {
                        // Make it visible
                        const wrapper = precision2.closest('[data-input="precision2"]');
                        if (wrapper) wrapper.style.display = 'block';
                        
                        // Try value "2" for renewal (common pattern)
                        precision2.value = "2";
                        precision2.dispatchEvent(new Event('change', { bubbles: true }));
                        
                        // If that doesn't work, find by text
                        const options = precision2.options;
                        for (let i = 0; i < options.length; i++) {
                            if (options[i].text.toLowerCase().includes('renouvellement')) {
                                precision2.value = options[i].value;
                                precision2.dispatchEvent(new Event('change', { bubbles: true }));
                                break;
                            }
                        }
                    }
                ''')
                page.wait_for_timeout(2000)
                renewal_selected = True
                logger.info("Renewal category selected via dropdown")
            except Exception as e:
                logger.warning(f"Dropdown renewal selection failed: {e}")
            
            # Approach 2: Try radio button selection
            if not renewal_selected:
                try:
                    # Look for renewal radio button
                    renewal_radio = page.locator('input[type="radio"][value*="renouvellement" i], label:has-text("Renouvellement")')
                    if renewal_radio.count() > 0:
                        renewal_radio.first.click(force=True)
                        page.wait_for_timeout(2000)
                        renewal_selected = True
                        logger.info("Renewal category selected via radio button")
                except Exception as e:
                    logger.warning(f"Radio button renewal selection failed: {e}")
            
            # Approach 3: Try clicking any element containing "renouvellement"
            if not renewal_selected:
                try:
                    renewal_element = page.locator('*:has-text("Tourisme / Court Séjour – Renouvellement")')
                    if renewal_element.count() > 0:
                        renewal_element.first.click(force=True)
                        page.wait_for_timeout(2000)
                        renewal_selected = True
                        logger.info("Renewal category selected via text element")
                except Exception as e:
                    logger.warning(f"Text element renewal selection failed: {e}")
            
            if renewal_selected:
                logger.info("Successfully selected renewal category")
            else:
                logger.warning("Could not confirm renewal category selection")
            
            # Try to go to next steps
            for attempt in range(3):
                try:
                    page.click('.next-step a:has-text("Suivant")', force=True, timeout=5000)
                    page.wait_for_timeout(3000)
                    logger.info(f"Clicked next button (attempt {attempt + 1})")
                except:
                    break
            
            # Try to skip services step if present
            try:
                page.click('input[value="me_delivery"]', force=True, timeout=3000)
                page.click('.next-step a:has-text("Suivant")', force=True, timeout=5000)
                page.wait_for_timeout(3000)
            except:
                pass
            
            return True
            
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return False

    def verify_true_availability(self, page):
        """Verify that dates are truly available, not just displayed"""
        try:
            # Wait for calendar to fully load
            page.wait_for_timeout(3000)
            
            # Method 1: Check for specific available date classes
            truly_available_dates = []
            
            # Look for dates that are clickable and not disabled
            available_selectors = [
                '.picker__day--infocus:not(.picker__day--disabled):not(.pickadate--full)',
                '.picker__day--infocus:not(.picker__day--disabled):not(.picker__day--unavailable)',
                '.picker__day[aria-disabled="false"]:not(.pickadate--full)',
                '.datepicker-day-button:not([disabled]):not(.is-disabled)',
                'td[data-pick]:not(.picker__day--disabled):not(.pickadate--full)'
            ]
            
            for selector in available_selectors:
                elements = page.locator(selector)
                count = elements.count()
                if count > 0:
                    logger.info(f"Found {count} potentially available dates with selector: {selector}")
                    
                    # Try to get actual date values
                    for i in range(min(count, 3)):  # Check first 3 dates
                        try:
                            element = elements.nth(i)
                            # Check if element is actually clickable
                            is_visible = element.is_visible()
                            is_enabled = element.is_enabled()
                            
                            if is_visible and is_enabled:
                                aria_label = element.get_attribute('aria-label')
                                data_pick = element.get_attribute('data-pick')
                                
                                if aria_label or data_pick:
                                    date_info = aria_label or data_pick
                                    truly_available_dates.append(date_info)
                                    logger.info(f"Verified available date: {date_info}")
                        except:
                            continue
            
            # Method 2: Check JavaScript state
            js_available_count = page.evaluate('''
                () => {
                    // Check for dates that are not disabled in the picker
                    const availableDates = document.querySelectorAll('.picker__day--infocus:not(.picker__day--disabled):not(.pickadate--full)');
                    const clickableDates = [];
                    
                    availableDates.forEach(date => {
                        const isDisabled = date.classList.contains('picker__day--disabled') ||
                                         date.classList.contains('pickadate--full') ||
                                         date.getAttribute('aria-disabled') === 'true';
                        
                        if (!isDisabled && date.offsetParent !== null) {  // Check if visible
                            clickableDates.push(date.getAttribute('aria-label') || date.textContent);
                        }
                    });
                    
                    return clickableDates.length;
                }
            ''')
            
            logger.info(f"JavaScript verification found {js_available_count} available dates")
            
            # Method 3: Check for "no availability" messages
            no_availability_messages = [
                "Aucune disponibilité",
                "No availability",
                "Pas de créneaux disponibles",
                "aucun créneau",
                "complet"
            ]
            
            page_content = page.content().lower()
            has_no_availability_message = any(msg.lower() in page_content for msg in no_availability_messages)
            
            if has_no_availability_message:
                logger.info("Found 'no availability' message on page")
                return 0, []
            
            # Combine all verification methods
            verified_count = len(truly_available_dates)
            
            # Only return positive if we have strong evidence of availability
            if verified_count > 0 and js_available_count > 0:
                logger.info(f"Verified {verified_count} truly available dates")
                return verified_count, truly_available_dates
            else:
                logger.info("No truly available dates found after verification")
                return 0, []
                
        except Exception as e:
            logger.error(f"Error verifying availability: {e}")
            return 0, []

    def check_renewal_calendar(self):
        """Check tourism renewal calendar for available dates"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)  # Set to False for debugging
            
            try:
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                page = context.new_page()
                page.set_default_timeout(30000)
                
                logger.info("Checking tourism RENEWAL calendar...")
                page.goto(self.base_url, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
                
                # Try to navigate to calendar
                navigation_success = self.navigate_to_renewal_calendar(page)
                
                if not navigation_success:
                    logger.warning("Could not navigate to renewal calendar")
                
                # Look for calendar regardless of navigation success
                page.wait_for_timeout(3000)
                
                # Take screenshot for debugging
                screenshot_path = f"renewal_calendar_{datetime.now().strftime('%H%M%S')}.png"
                page.screenshot(path=screenshot_path)
                logger.info(f"Screenshot saved: {screenshot_path}")
                
                # Check if we're on the renewal page
                page_content = page.content()
                on_renewal_page = 'renouvellement' in page_content.lower()
                
                if not on_renewal_page:
                    logger.warning("Not on renewal page - may be checking wrong category")
                else:
                    logger.info("Confirmed on renewal page")
                
                # Check for calendar elements
                calendar_found = False
                calendar_selectors = [
                    'input.datepicker_date',
                    'input[name="date"]',
                    '.picker__holder',
                    '.picker__box',
                    '[data-pick]'
                ]
                
                for selector in calendar_selectors:
                    elements = page.locator(selector)
                    if elements.count() > 0:
                        logger.info(f"Calendar element found: {selector}")
                        calendar_found = True
                        break
                
                if calendar_found:
                    # Try to open calendar if needed
                    try:
                        date_input = page.locator('input.datepicker_date, input[name="date"]').first
                        if date_input.count() > 0:
                            date_input.click(timeout=5000)
                            page.wait_for_timeout(2000)
                            logger.info("Clicked on date picker to open calendar")
                    except:
                        pass
                    
                    # Verify true availability
                    available_count, available_dates = self.verify_true_availability(page)
                    
                    # Check for time slots
                    time_options = page.locator('select[name="time"] option[value]:not([value=""])')
                    available_times = time_options.count()
                    
                    logger.info(f"Final verification: {available_count} verified dates, {available_times} time slots")
                    
                    # Only alert if we have verified available dates
                    if available_count > 0:
                        # Get time slot examples
                        example_times = []
                        for i in range(min(available_times, 5)):
                            try:
                                time_element = time_options.nth(i)
                                time_value = time_element.inner_text()
                                if time_value:
                                    example_times.append(time_value)
                            except:
                                continue
                        
                        message = f"""
🎉 TOURISM RENEWAL APPOINTMENTS AVAILABLE!

✅ Category: Tourisme / Court Séjour – Renouvellement
✅ VERIFIED Available dates: {available_count}
✅ Available time slots: {available_times}

Example dates: {', '.join(available_dates[:5])}
Example times: {', '.join(example_times)}

Book immediately: {self.base_url}
Type: Tourisme / Court Séjour – Renouvellement
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

⚠️ This is a VERIFIED availability - dates have been confirmed as clickable!
                        """
                        
                        self.send_email_notification("🎉 VERIFIED TOURISM RENEWAL APPOINTMENTS!", message)
                        self.send_telegram_notification(message)
                        
                        result = {
                            'timestamp': datetime.now().isoformat(),
                            'status': 'RENEWAL_AVAILABLE_VERIFIED',
                            'category': 'Tourisme / Court Séjour – Renouvellement',
                            'verified_dates': available_count,
                            'available_times': available_times,
                            'example_dates': available_dates[:5],
                            'example_times': example_times
                        }
                        self.results.append(result)
                        return True
                    else:
                        logger.info("Calendar found but NO verified available dates for renewal")
                        result = {
                            'timestamp': datetime.now().isoformat(),
                            'status': 'RENEWAL_CALENDAR_FULL',
                            'category': 'Tourisme / Court Séjour – Renouvellement',
                            'message': 'Calendar accessible but no verified available dates'
                        }
                        self.results.append(result)
                        return False
                else:
                    logger.info("No calendar elements detected")
                    result = {
                        'timestamp': datetime.now().isoformat(),
                        'status': 'NO_RENEWAL_CALENDAR',
                        'category': 'Tourisme / Court Séjour – Renouvellement',
                        'message': 'Could not find calendar elements'
                    }
                    self.results.append(result)
                    return False
                
            except Exception as e:
                logger.error(f"Error checking renewal calendar: {e}")
                return False
                
            finally:
                browser.close()

    def save_results_to_csv(self):
        """Save monitoring results to CSV"""
        if self.results:
            df = pd.DataFrame(self.results)
            filename = f"tourism_renewal_{datetime.now().strftime('%Y%m%d')}.csv"
            df.to_csv(filename, index=False)
            logger.info(f"Results saved to {filename}")

    def run_continuous_monitoring(self):
        """Run continuous monitoring loop for renewal category only"""
        logger.info("Starting tourism RENEWAL monitoring with verification...")
        logger.info(f"Checking every {self.config['monitoring']['check_interval']} seconds")
        logger.info("Monitoring: Tourisme / Court Séjour – Renouvellement ONLY")
        logger.info("FALSE POSITIVE PROTECTION: Only alerting on VERIFIED available dates")
        
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while True:
            try:
                logger.info(f"Checking renewal calendar at {datetime.now()}")
                
                appointments_available = self.check_renewal_calendar()
                
                if appointments_available:
                    logger.info("🎉 VERIFIED RENEWAL APPOINTMENTS FOUND!")
                    consecutive_errors = 0
                else:
                    logger.info("No verified renewal appointments available")
                
                # Save results periodically
                if len(self.results) > 0 and len(self.results) % 10 == 0:
                    self.save_results_to_csv()
                
                logger.info(f"Waiting {self.config['monitoring']['check_interval']} seconds...")
                time.sleep(self.config['monitoring']['check_interval'])
                
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error in monitoring loop: {e} (Error {consecutive_errors}/{max_consecutive_errors})")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("Too many consecutive errors. Stopping monitoring.")
                    break
                    
                time.sleep(60)
        
        self.save_results_to_csv()

def main():
    """Main function"""
    monitor = TourismRenewalMonitor()
    
    print("""
    🔄 Tourism RENEWAL Calendar Monitor (v2.0)
    ===========================================
    
    Monitors ONLY for:
    • Tourisme / Court Séjour – Renouvellement
    
    Features:
    • FALSE POSITIVE PROTECTION
    • Verifies dates are truly clickable
    • Screenshots for debugging
    • Enhanced logging
    
    Configuration file: config.json
    Log file: tourism_renewal_calendar.log
    """)
    
    choice = input("Start tourism RENEWAL monitoring with verification? (y/n): ").lower().strip()
    
    if choice == 'y':
        try:
            monitor.run_continuous_monitoring()
        except KeyboardInterrupt:
            print("\nMonitoring stopped.")
    else:
        print("Cancelled.")

if __name__ == "__main__":
    main()