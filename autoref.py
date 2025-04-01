import requests
import json
import time
import random
from eth_account import Account
import os
from termcolor import colored

class MonadScoreRegistration:
    def __init__(self, invite_code='MEybc453', proxies=None):
        self.base_url = 'https://mscore.onrender.com'
        self.invite_code = invite_code
        self.proxies = proxies or []
        
        # Updated headers to include all the headers from your curl example
        self.headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-US,en;q=0.9,id;q=0.8',
            'cache-control': 'no-cache',
            'content-type': 'application/json',
            'origin': 'https://monadscore.xyz',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': 'https://monadscore.xyz/',
            'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
        }

    def generate_wallet(self):
        account = Account.create()
        return {
            'address': account.address,
            'private_key': account._private_key.hex()
        }

    def get_proxy(self):
        if not self.proxies:
            return None
        proxy = random.choice(self.proxies)
        print(colored(f"🌐 Using Proxy: {proxy}", "cyan"))
        return {'http': proxy, 'https': proxy}

    def simulate_delay(self, min_delay=1, max_delay=3):
        delay = random.uniform(min_delay, max_delay)
        print(colored(f"⏱️ Waiting {delay:.2f}s...", "cyan"))
        time.sleep(delay)

    def register_user(self, wallet, invite_code, proxy=None, max_retries=5):
        url = f'{self.base_url}/user'
        payload = {'wallet': wallet, 'invite': invite_code}
        
        for attempt in range(max_retries):
            try:
                print(colored(f"📡 Registering wallet (Attempt {attempt+1}/{max_retries})...", "cyan"))
                # Use a longer delay for registration
                self.simulate_delay(3, 5)
                
                response = requests.post(url, headers=self.headers, json=payload, proxies=proxy, timeout=60)
                response_data = response.json()
                
                # Check for error response
                if 'error' in response_data:
                    print(colored(f"⚠️ API Error: {response_data['error']}", "red"))
                    self.simulate_delay(5, 10)
                    continue
                
                # Check if we got a proper response with user data
                if 'user' in response_data and 'referralCode' in response_data['user']:
                    ref_code = response_data['user']['referralCode']
                    print(colored(f"🚀 Registered: {wallet[:10]}... (Ref: {ref_code})", "green"))
                    return response_data
                else:
                    print(colored(f"⚠️ Incomplete response on attempt {attempt+1}, retrying...", "yellow"))
                    print(colored(f"Response: {response_data}", "yellow"))
                    # Wait longer between retries
                    self.simulate_delay(5, 10)
            except Exception as e:
                print(colored(f"❌ Error on attempt {attempt+1}: {e}", "red"))
                self.simulate_delay(5, 15)
        
        # If we reach here, all attempts failed
        print(colored(f"⛔ Failed to register wallet after {max_retries} attempts", "red"))
        return {"user": {"referralCode": "N/A"}}

    def claim_tasks(self, wallet, proxy=None, max_retries=3):
        task_ids = ['task001', 'task002', 'task003']
        for task_id in task_ids:
            url = f'{self.base_url}/user/claim-task'
            payload = {'wallet': wallet, 'taskId': task_id}
            
            for attempt in range(max_retries):
                try:
                    self.simulate_delay(3, 5)
                    response = requests.post(url, headers=self.headers, json=payload, proxies=proxy, timeout=30)
                    print(colored(f"🎯 Claimed {task_id}: {wallet[:10]}...", "blue"))
                    break
                except Exception as e:
                    print(colored(f"❌ Error claiming task {task_id} (attempt {attempt+1}): {e}", "red"))
                    self.simulate_delay(5, 10)

    def activate_node(self, wallet, proxy=None, max_retries=3):
        url = f'{self.base_url}/user/update-start-time'
        payload = {
            'wallet': wallet,
            'startTime': int(time.time() * 1000)
        }
        
        for attempt in range(max_retries):
            try:
                self.simulate_delay(3, 5)
                response = requests.put(url, headers=self.headers, json=payload, proxies=proxy, timeout=30)
                print(colored(f"🔋 Activated: {wallet[:10]}...", "yellow"))
                break
            except Exception as e:
                print(colored(f"❌ Error activating node (attempt {attempt+1}): {e}", "red"))
                self.simulate_delay(5, 10)

    def process_registration(self):
        proxy = self.get_proxy()
        wallet_info = self.generate_wallet()
        wallet = wallet_info['address']

        register_response = self.register_user(wallet, self.invite_code, proxy)
        
        # Extract referral code directly from the user object in the response
        referral_code = 'N/A'
        if 'user' in register_response and 'referralCode' in register_response['user']:
            referral_code = register_response['user']['referralCode']
        
        self.claim_tasks(wallet, proxy)
        self.activate_node(wallet, proxy)
        
        return {
            'address': wallet_info['address'],
            'private_key': wallet_info['private_key'],
            'referralCode': referral_code
        }

    def verify_registration(self, wallet, proxy=None, max_retries=3):
        """Verify that a wallet was properly registered and get the referral code"""
        url = f'{self.base_url}/user/{wallet}'
        
        for attempt in range(max_retries):
            try:
                print(colored(f"🔍 Verifying registration (Attempt {attempt+1}/{max_retries})...", "cyan"))
                self.simulate_delay(5, 10)
                
                response = requests.get(url, headers=self.headers, proxies=proxy, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    if 'user' in data and 'referralCode' in data['user']:
                        return data['user']['referralCode']
            except Exception as e:
                print(colored(f"❌ Error verifying registration (attempt {attempt+1}): {e}", "red"))
                self.simulate_delay(5, 10)
        
        return 'N/A'

    def bulk_register(self, num_registrations):
        results = []
        
        try:
            with open('monad_registrations.json', 'r') as f:
                results = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            results = []

        for i in range(num_registrations):
            print(colored(f"🌟 Registration {i+1}/{num_registrations}", "magenta"))
            
            try:
                registration = self.process_registration()
                
                # If referral code is N/A, try to verify it again
                if registration['referralCode'] == 'N/A':
                    print(colored("⚠️ Referral code not found in initial response, verifying again...", "yellow"))
                    registration['referralCode'] = self.verify_registration(registration['address'], self.get_proxy())
                
                results.append(registration)
                
                with open('monad_registrations.json', 'w') as f:
                    json.dump(results, f, indent=2)
                
                delay = random.uniform(10, 30)  # Longer delay between registrations
                print(colored(f"⏳ Waiting {delay:.2f}s before next registration...", "cyan"))
                time.sleep(delay)
                
            except Exception as e:
                print(colored(f"❌ Error during registration: {e}", "red"))
                time.sleep(random.uniform(30, 60))  # Even longer delay after errors
        
        return results

def load_proxies(file_path='proxy.txt'):
    try:
        with open(file_path, 'r') as f:
            proxies = [line.strip() for line in f if line.strip()]
        print(colored(f"🌍 Loaded {len(proxies)} proxies", "green"))
        return proxies
    except FileNotFoundError:
        print(colored("🚫 No proxy file found. Running without proxies.", "yellow"))
        return []

def main():
    proxies = load_proxies()
    
    while True:
        try:
            num_registrations = int(input("How many registrations? "))
            if num_registrations > 0:
                break
            print("Please enter a positive number.")
        except ValueError:
            print("Please enter a valid number.")
    
    registrar = MonadScoreRegistration(proxies=proxies)
    registrations = registrar.bulk_register(num_registrations)
    
    print(colored(f"✨ Completed {len(registrations)} registrations!", "green"))

if __name__ == "__main__":
    main()