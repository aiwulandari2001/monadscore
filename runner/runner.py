import json
import requests
from requests.exceptions import RequestException
from datetime import datetime, timezone, timedelta
import time
import schedule
import logging
from logging.handlers import RotatingFileHandler
import traceback
import random
import colorama
from colorama import Fore, Style
import os

# Initialize colorama for colored console output
colorama.init(autoreset=True)

class WalletUpdater:
    def __init__(self, registrations_file, proxies_file='proxy.txt', proxy_type='socks5'):
        # Setup logging
        self.setup_logging()
        
        # Load wallet registrations from JSON file
        self.load_registrations(registrations_file)
        
        # Set proxy type (default to socks5)
        self.proxy_type = proxy_type.lower()
        self.logger.info(f"Using proxy type: {self.proxy_type}")
        self.print_status(f"🔌 Using proxy type: {self.proxy_type}", Fore.CYAN)
        
        # Load proxies
        self.load_proxies(proxies_file)
        
        # API endpoints
        self.update_url = 'https://mscore.onrender.com/user/update-start-time'
        self.login_url = 'https://mscore.onrender.com/user/login'
        
        # Max retries and backoff settings
        self.max_retries = 5
        self.base_backoff = 15  # seconds
        
        # Timeout settings
        self.request_timeout = 120  # seconds
        
        # Shorter delay between wallets (1-3 seconds)
        self.min_delay = 1
        self.max_delay = 3
    
    def print_status(self, message, color=Fore.WHITE, emoji=""):
        """Print colored status messages with emojis"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{color}[{timestamp}] {emoji} {message}{Style.RESET_ALL}")
    
    def setup_logging(self):
        """Configure logging to track script activities"""
        # Create logger
        self.logger = logging.getLogger('WalletUpdater')
        self.logger.setLevel(logging.INFO)
        
        # Create file handler with log rotation
        file_handler = RotatingFileHandler(
            'wallet_update.log', 
            maxBytes=1024 * 1024 * 10,  # 10 MB
            backupCount=5
        )
        file_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s: %(message)s', 
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        self.logger.addHandler(file_handler)
    
    def load_proxies(self, proxies_file):
        """Load proxies from text file"""
        try:
            with open(proxies_file, 'r') as file:
                # Expect proxies in format: ip:port or ip:port:username:password
                self.proxies = [line.strip() for line in file if line.strip()]
            
            self.logger.info(f"Loaded {len(self.proxies)} proxies")
            self.print_status(f"📋 Loaded {len(self.proxies)} proxies", Fore.GREEN)
        except Exception as e:
            self.logger.error(f"Failed to load proxies: {e}")
            self.print_status(f"❌ Failed to load proxies: {e}", Fore.RED)
            self.proxies = []
    
    def get_proxy_dict(self, proxy_str):
        """Convert proxy string to dictionary for requests"""
        try:
            parts = proxy_str.split(':')
            
            # Determine protocol prefix based on proxy_type
            protocol_prefix = f"{self.proxy_type}://"
            
            if len(parts) == 2:
                # IP:PORT format
                return {
                    'http': f'{protocol_prefix}{parts[0]}:{parts[1]}',
                    'https': f'{protocol_prefix}{parts[0]}:{parts[1]}'
                }
            elif len(parts) == 4:
                # IP:PORT:USERNAME:PASSWORD format
                if self.proxy_type == 'socks5':
                    # For SOCKS5, format is socks5://username:password@host:port
                    return {
                        'http': f'{protocol_prefix}{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}',
                        'https': f'{protocol_prefix}{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}'
                    }
                else:
                    # For HTTP, format is http://username:password@host:port
                    return {
                        'http': f'{protocol_prefix}{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}',
                        'https': f'{protocol_prefix}{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}'
                    }
            else:
                self.logger.error(f"Invalid proxy format: {proxy_str}")
                return None
        except Exception as e:
            self.logger.error(f"Error parsing proxy {proxy_str}: {str(e)}")
            return None
    
    def load_registrations(self, registrations_file):
        """Load wallet registrations from JSON file"""
        try:
            with open(registrations_file, 'r') as file:
                self.wallet_registrations = json.load(file)
            self.logger.info(f"Loaded {len(self.wallet_registrations)} wallet registrations")
            self.print_status(f"💼 Loaded {len(self.wallet_registrations)} wallet registrations", Fore.GREEN)
        except Exception as e:
            self.logger.error(f"Failed to load registrations: {e}")
            self.print_status(f"❌ Failed to load registrations: {e}", Fore.RED)
            self.wallet_registrations = []
    
    def get_current_utc_timestamp(self):
        """Get current timestamp in milliseconds for UTC 00:00"""
        now = datetime.now(timezone.utc)
        # Reset to start of the current day in UTC
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return int(today_start.timestamp() * 1000)
    
    def make_request(self, url, method, payload, headers, proxy=None, retry_count=0):
        """Make API request with retry and backoff logic"""
        use_proxy = proxy is not None
        proxy_str = str(proxy) if use_proxy else "Direct"
        start_time = time.time()
        
        try:
            # Calculate backoff time with exponential backoff
            if retry_count > 0:
                backoff_time = self.base_backoff * (2 ** (retry_count - 1))
                # Add some jitter (random delay)
                backoff_time = backoff_time + random.uniform(0, 5)
                self.logger.info(f"Retry #{retry_count} for {payload['wallet']} - Backing off for {backoff_time:.2f} seconds")
                if retry_count == 1:  # Only show first retry in console
                    self.print_status(f"🔄 Retrying for {payload['wallet']} in {backoff_time:.1f}s", Fore.YELLOW)
                time.sleep(backoff_time)
            
            # Log the request attempt
            self.logger.info(f"Sending {method} request to {url} for {payload['wallet']} with timeout {self.request_timeout}s (Attempt {retry_count + 1}/{self.max_retries + 1})")
            
            # Send request with or without proxy
            if use_proxy:
                # For SOCKS5 proxies, ensure the dependency is installed
                if self.proxy_type == 'socks5':
                    try:
                        import socks
                    except ImportError:
                        self.logger.warning("PySocks not installed. Required for SOCKS5 proxies.")
                        return {'address': payload['wallet'], 'status': 'Failed', 'error': 'PySocks not installed'}
                
                if method.upper() == 'PUT':
                    response = requests.put(
                        url, 
                        headers=headers, 
                        json=payload,
                        proxies=proxy,
                        timeout=self.request_timeout
                    )
                else:  # POST
                    response = requests.post(
                        url, 
                        headers=headers, 
                        json=payload,
                        proxies=proxy,
                        timeout=self.request_timeout
                    )
            else:
                if method.upper() == 'PUT':
                    response = requests.put(
                        url, 
                        headers=headers, 
                        json=payload,
                        timeout=self.request_timeout
                    )
                else:  # POST
                    response = requests.post(
                        url, 
                        headers=headers, 
                        json=payload,
                        timeout=self.request_timeout
                    )
            
            elapsed_time = time.time() - start_time
            self.logger.info(f"Request for {payload['wallet']} completed in {elapsed_time:.2f} seconds")
            
            # Store the full response text for debugging
            full_response_text = response.text
            
            # Handle specific status codes
            if response.status_code == 429:  # Too Many Requests
                if retry_count < self.max_retries:
                    self.logger.warning(f"Rate limited (429) for {payload['wallet']} - Will retry")
                    # Try again with backoff
                    return self.make_request(url, method, payload, headers, proxy, retry_count + 1)
                else:
                    self.logger.error(f"Rate limit exceeded after {self.max_retries} retries for {payload['wallet']}")
            
            # Try to parse response JSON
            response_data = {}
            try:
                if response.text and response.text.strip():
                    response_data = response.json()
                else:
                    self.logger.warning(f"Empty response for {payload['wallet']}")
                    response_data = {"error": "Empty response"}
            except ValueError as json_error:
                self.logger.warning(f"Failed to parse JSON for {payload['wallet']} (Status: {response.status_code}): {str(json_error)}")
                # Store the raw response text for debugging
                response_data = {"error": "Invalid JSON response", "raw_response": response.text[:500]}
            
            return {
                'address': payload['wallet'],
                'status': 'Success' if response.status_code == 200 else 'Failed',
                'status_code': response.status_code,
                'proxy': proxy_str,
                'response': response_data,
                'retry_count': retry_count,
                'raw_response': full_response_text,
                'elapsed_time': elapsed_time
            }
            
        except RequestException as e:
            elapsed_time = time.time() - start_time
            self.logger.error(f"Request error for {payload['wallet']} with {proxy_str} after {elapsed_time:.2f}s: {e}")
            
            # Retry with backoff if we haven't reached max retries
            if retry_count < self.max_retries:
                return self.make_request(url, method, payload, headers, proxy, retry_count + 1)
            
            return {
                'address': payload['wallet'],
                'status': 'Failed',
                'error': str(e),
                'proxy': proxy_str,
                'retry_count': retry_count,
                'elapsed_time': elapsed_time
            }
    
    def get_wallet_metrics(self, wallet_address, proxy=None):
        """Fetch wallet metrics using the login endpoint"""
        headers = {
            'accept': 'application/json, text/plain, */*',
            'content-type': 'application/json',
            'origin': 'https://monadscore.xyz',
            'referer': 'https://monadscore.xyz/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
        }
        
        payload = {
            'wallet': wallet_address
        }
        
        # Add a small delay before making the login request to avoid rate limiting
        time.sleep(random.uniform(0.5, 1.5))
        
        return self.make_request(self.login_url, 'POST', payload, headers, proxy)
    
    def update_start_time(self):
        """Update start time for all wallets in the registrations"""
        self.logger.info(f"Scheduled task triggered at {datetime.now(timezone.utc)}")
        
        # Clear screen for better visibility
        os.system('cls' if os.name == 'nt' else 'clear')
        
        self.print_status(f"⏰ DAILY UPDATE STARTED", Fore.MAGENTA, "🚀")
        print(f"{Fore.MAGENTA}{'=' * 60}{Style.RESET_ALL}")
        
        # Ensure we have registrations to process
        if not self.wallet_registrations:
            self.logger.warning("No wallet registrations found. Skipping update.")
            self.print_status("❌ No wallet registrations found. Skipping update.", Fore.RED)
            return []
        
        # Prepare headers
        headers = {
            'accept': 'application/json, text/plain, */*',
            'content-type': 'application/json',
            'origin': 'https://monadscore.xyz',
            'referer': 'https://monadscore.xyz/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
        }
        
        # Timestamp for all updates
        start_time = self.get_current_utc_timestamp()
        
        # Track results
        results = []
        
        # Process each wallet registration
        for i, registration in enumerate(self.wallet_registrations):
            # Add a progress indicator
            progress = f"[{i+1}/{len(self.wallet_registrations)}]"
            self.print_status(f"{progress} 🔄 Processing wallet: {registration['address'][:8]}...{registration['address'][-6:]}", Fore.CYAN)
            
            # Add short delay between wallets (1-3 seconds)
            if i > 0:
                delay = random.uniform(self.min_delay, self.max_delay)
                time.sleep(delay)
            
            # Prepare payload for update-start-time
            update_payload = {
                'wallet': registration['address'],
                'startTime': start_time
            }
            
            update_result = None
            metrics_result = None
            current_proxy = None
            
            # Try with proxy first if available
            if self.proxies:
                proxy_str = random.choice(self.proxies)
                current_proxy = self.get_proxy_dict(proxy_str)
                
                if current_proxy:
                    update_result = self.make_request(self.update_url, 'PUT', update_payload, headers, current_proxy)
            
            # If no proxy available or proxy failed, try without proxy
            if update_result is None or update_result['status'] == 'Failed':
                direct_result = self.make_request(self.update_url, 'PUT', update_payload, headers)
                
                # Use direct result if either no proxy was used or proxy failed
                if update_result is None or (direct_result['status'] == 'Success' and update_result['status'] == 'Failed'):
                    update_result = direct_result
                    current_proxy = None  # Reset proxy for metrics call
            
            # Now fetch metrics using the same proxy if successful, or no proxy if failed
            metrics_result = self.get_wallet_metrics(registration['address'], current_proxy)
            
            # Combine results
            result = update_result.copy()
            
            # Add metrics from the login endpoint response
            if metrics_result and 'response' in metrics_result and isinstance(metrics_result['response'], dict):
                # Extract user object from the response
                metrics_data = metrics_result['response'].get('user', {})
                
                # Extract specific fields we need
                metrics = {
                    'totalPoints': metrics_data.get('totalPoints', 'N/A'),
                    'nodeUptime': metrics_data.get('nodeUptime', 'N/A'),
                    'activeDays': metrics_data.get('activeDays', 'N/A'),
                    'checkInStreak': metrics_data.get('checkInStreak', 'N/A'),
                    'updatedAt': metrics_data.get('updatedAt', 'N/A')
                }
                
                result['metrics'] = metrics
            else:
                # Default metrics if we couldn't get them
                result['metrics'] = {
                    'totalPoints': 'N/A',
                    'nodeUptime': 'N/A',
                    'activeDays': 'N/A',
                    'checkInStreak': 'N/A',
                    'updatedAt': 'N/A'
                }
            
            # Add referral code to result
            result['referral_code'] = registration.get('referralCode', 'N/A')
            
            # Display result status with emoji
            status_emoji = "✅" if result['status'] == 'Success' else "❌"
            status_color = Fore.GREEN if result['status'] == 'Success' else Fore.RED
            
            print(f"{Fore.YELLOW}{'▶'} {Fore.WHITE}Wallet: {Fore.CYAN}{registration['address'][:8]}...{registration['address'][-6:]}")
            self.print_status(f"Status: {result['status']}", status_color, status_emoji)
            
            # Display metrics in a clean format
            print(f"{Fore.YELLOW}{'▶'} {Fore.BLUE}Points: {Fore.GREEN}{result['metrics']['totalPoints']} {Fore.BLUE}| " 
                  f"Uptime: {Fore.GREEN}{result['metrics']['nodeUptime']} {Fore.BLUE}| "
                  f"Days: {Fore.GREEN}{result['metrics']['activeDays']} {Fore.BLUE}| "
                  f"Streak: {Fore.GREEN}{result['metrics']['checkInStreak']}")
            
            print(f"{Fore.CYAN}{'-' * 60}{Style.RESET_ALL}")
            
            # Add to results
            results.append(result)
        
        # Save results to file
        try:
            # Create a clean version of results for the JSON file
            clean_results = []
            for r in results:
                clean_r = r.copy()
                # Remove potentially large raw response
                if 'raw_response' in clean_r:
                    del clean_r['raw_response']
                if 'response' in clean_r and isinstance(clean_r['response'], dict) and 'raw_response' in clean_r['response']:
                    clean_r['response'] = {k: v for k, v in clean_r['response'].items() if k != 'raw_response'}
                clean_results.append(clean_r)
                
            with open('wallet_update_results.json', 'w') as f:
                json.dump(clean_results, f, indent=2)
            self.logger.info("Results saved to wallet_update_results.json")
            self.print_status("Results saved to wallet_update_results.json", Fore.GREEN, "💾")
        except Exception as e:
            self.logger.error(f"Failed to save results: {e}")
            self.print_status(f"Failed to save results: {e}", Fore.RED, "❌")
        
        # Log summary
        success_count = sum(1 for r in results if r['status'] == 'Success')
        self.logger.info(f"Update completed. Success: {success_count}/{len(results)}")
        self.print_status(f"Update completed. Success: {success_count}/{len(results)}", 
                          Fore.GREEN if success_count == len(results) else Fore.YELLOW, 
                          "🎉" if success_count == len(results) else "⚠️")
        
        print(f"{Fore.MAGENTA}{'=' * 60}{Style.RESET_ALL}")
        
        return results

def calculate_time_until_next_run():
    """Calculate time until the next scheduled run at 00:00 UTC"""
    now = datetime.now(timezone.utc)
    # Calculate tomorrow at 00:00 UTC
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # If it's before midnight UTC today, use today's midnight
    today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # If we're past today's midnight, use tomorrow's
    next_run = tomorrow if now > today_midnight else today_midnight
    
    # Calculate time difference
    time_diff = next_run - now
    
    # Convert to hours, minutes, seconds
    hours, remainder = divmod(time_diff.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    return int(hours), int(minutes), int(seconds), next_run

def main():
    # Path to your wallet registrations JSON file
    registrations_file = 'monad_registrations.json'
    
    try:
        # Clear screen for better visibility
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print(f"{Fore.CYAN}{'=' * 60}")
        print(f"{Fore.CYAN}{'🌙'} {Fore.YELLOW}MONAD SCORE WALLET UPDATER {Fore.CYAN}{'🌙'}")
        print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}")
        
        # Default to SOCKS5 proxy type
        proxy_type = 'socks5'
        print(f"{Fore.GREEN}🔌 Using SOCKS5 proxy by default{Style.RESET_ALL}")
        
        # Create updater with specified proxy type
        updater = WalletUpdater(registrations_file, proxy_type=proxy_type)
        
        # Set up the scheduler to run at UTC midnight
        schedule.clear()
        schedule.every().day.at("00:00").do(updater.update_start_time)
        
        # Check if dependencies are installed for SOCKS5
        try:
            import socks
            print(f"{Fore.GREEN}✅ PySocks is installed - SOCKS5 proxies are ready{Style.RESET_ALL}")
        except ImportError:
            print(f"{Fore.RED}⚠️ PySocks not installed. Required for SOCKS5 proxies.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Installing PySocks now...{Style.RESET_ALL}")
            import subprocess
            try:
                subprocess.check_call(["pip", "install", "requests[socks]"])
                print(f"{Fore.GREEN}✅ PySocks installed successfully.{Style.RESET_ALL}")
            except:
                print(f"{Fore.RED}❌ Failed to install PySocks. SOCKS5 proxies may not work correctly.{Style.RESET_ALL}")
        
        # Option to run immediately
        print(f"\n{Fore.YELLOW}Do you want to run the update immediately? (y/n):{Style.RESET_ALL}", end=" ")
        run_now = input().lower() == 'y'
        if run_now:
            print(f"{Fore.GREEN}Running update immediately...{Style.RESET_ALL}")
            updater.update_start_time()
        
        print(f"\n{Fore.CYAN}Scheduler started. Waiting for next update at 00:00 UTC")
        print(f"{Fore.YELLOW}Press Ctrl+C to exit{Style.RESET_ALL}")
        
        last_seconds = -1  # To control display updates
        
        # Keep the script running
        while True:
            # Run any pending scheduled tasks
            schedule.run_pending()
            
            # Calculate and display countdown
            hours, minutes, seconds, next_run = calculate_time_until_next_run()
            
            # Update display every second
            if seconds != last_seconds:
                next_run_str = next_run.strftime("%Y-%m-%d %H:%M:%S UTC")
                countdown = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                print(f"\r{Fore.CYAN}⏱️ Next update in: {Fore.YELLOW}{countdown} {Fore.CYAN}at {Fore.GREEN}{next_run_str}", end="")
                last_seconds = seconds
            
            time.sleep(1)
    
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}Script terminated by user{Style.RESET_ALL}")
    except Exception as e:
        logging.error(f"Unhandled exception: {e}")
        logging.error(traceback.format_exc())
        print(f"\n{Fore.RED}❌ An error occurred: {e}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Check the log file for details{Style.RESET_ALL}")
        time.sleep(5)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}Script terminated by user{Style.RESET_ALL}")
    except Exception as e:
        logging.error(f"Unhandled exception: {e}")
        logging.error(traceback.format_exc())
        print(f"\n{Fore.RED}❌ Critical error: {e}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Check the log file for details{Style.RESET_ALL}")
        time.sleep(5)