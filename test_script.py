import os
import sqlite3
import re
import json
import time
import shlex
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Type, Any, List, Dict
import urllib.request
import urllib.error

from dotenv import load_dotenv
from langchain_core.tools import BaseTool, Tool
from pydantic import BaseModel, Field, model_validator
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import SerpAPIWrapper
from langchain_community.tools.tavily_search import TavilySearchResults
from googleapiclient.discovery import build
import asyncio
from browser_use import Agent, BrowserProfile
from langchain_google_genai import ChatGoogleGenerativeAI
from browser_use.llm.google.chat import ChatGoogle
from langchain.agents import AgentExecutor, create_tool_calling_agent, create_react_agent
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.messages import HumanMessage, AIMessage

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path, override=True)

# --- Database Setup ---
DB_NAME = "products.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Products table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            store TEXT,
            price TEXT,
            url TEXT,
            description TEXT,
            model_number TEXT,
            release_date TEXT,
            ram TEXT,
            ssd TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Check if columns exist (for migration)
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN model_number TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN release_date TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN ram TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN ssd TEXT")
    except sqlite3.OperationalError:
        pass
    
    # Agent logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            query TEXT,
            scratchpad TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize the database
init_db()

# --- Helper Functions ---

class TavilySearchWrapper:
    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY")
        if not self.api_key:
             raise ValueError("TAVILY_API_KEY must be set for Tavily Search.")
        self.tool = TavilySearchResults(api_key=self.api_key)

    def run(self, query: str) -> str:
        try:
            results = self.tool.invoke({"query": query})
            
            formatted_results = []
            for item in results:
                content = item.get('content')
                url = item.get('url')
                formatted_results.append(f"Content: {content}\nURL: {url}\n")
            
            return "\n".join(formatted_results) if formatted_results else "No results found."
        except Exception as e:
            return f"Error during Tavily Search: {e}"

class BrowserUseSearchWrapper:
    def __init__(self):
        model_name = os.getenv("MODEL_NAME", "gemini-2.0-flash")
        self.llm = ChatGoogle(model=model_name, api_key=os.getenv("GOOGLE_API_KEY"))
        
        # CAPTCHA回避設定
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.browser_profile = BrowserProfile(headless=False, user_agent=user_agent)

    async def _search_async(self, query: str) -> str:
        task = f"""
        Web全体から '{query}' を検索してください。
        検索結果の上位の製品について、以下の情報を確実に抽出してください：
        1. 製品名（タイトル）
        2. 正確な製品ページのURL
        3. 詳細な製品概要（スペックや特徴）
        4. 価格
        5. 型番（モデル番号）
        6. 発売日

        重要：URLと製品概要は必須です。URLは必ず http または https で始まる有効なものを取得してください。
        型番や発売日が見つかる場合はそれらも必ず抽出してください。
        検索結果ページだけでなく、必要であれば個別の製品ページにアクセスして情報を取得してください。
        ページが完全に読み込まれるまで待ち、正確な情報を取得するようにしてください。
        また、メモリ（RAM）やストレージ（SSDなど）の容量を抽出する際、「最大〇〇GB」「〇〇GBまで増設可能」などと記載されている拡張上限の数値は対象外とし、必ず「標準搭載（初期状態）」の容量を抽出してください。
        
        【極密事項】
        ページ内に以下の文言が含まれている商品は「販売不可」とみなし、絶対に抽出・出力しないでください。
        - 「販売終了」
        - 「お探しのページは見つかりません」
        - 「404 Not Found」
        - 「この商品は現在お取り扱いできません」
        """
        agent = Agent(task=task, llm=self.llm, browser_profile=self.browser_profile)
        result = await agent.run()
        return result.final_result()

    def run(self, query: str) -> str:
        try:
            return asyncio.run(self._search_async(query))
        except Exception as e:
            return f"Error during Browser Use Search: {e}"

def get_search_tool_func():
    provider = os.getenv("SEARCH_PROVIDER", "serpapi")
    if provider == "tavily_api":
        return TavilySearchWrapper()
    elif provider == "browser_use":
        return BrowserUseSearchWrapper()
    else:
        return SerpAPIWrapper()

def get_all_products():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, store, price, url, description, model_number, release_date, ram, ssd, updated_at FROM products")
    rows = cursor.fetchall()
    conn.close()
    products = []
    for r in rows:
        products.append({
            'id': r[0],
            'name': r[1],
            'store': r[2],
            'price': r[3],
            'url': r[4],
            'description': r[5],
            'model_number': r[6] if len(r) > 6 else "",
            'release_date': r[7] if len(r) > 7 else "",
            'ram': r[8] if len(r) > 8 else "",
            'ssd': r[9] if len(r) > 9 else "",
            'updated_at': r[10] if len(r) > 10 else ""
        })
    return products

def parse_price_val(p_str):
    if not p_str:
        return float('inf')
    s = str(p_str).replace(',', '')
    
    # Handle "万" (ten thousand)
    # Match patterns like "1.5万", "10万"
    match_man = re.search(r'(\d+(\.\d+)?)万', s)
    if match_man:
        try:
            val = float(match_man.group(1)) * 10000
            return int(val)
        except:
            pass
            
    # Fallback: extract all digits and join them
    nums = re.findall(r'\d+', s)
    return int(''.join(nums)) if nums else float('inf')

def extract_alphanumeric(s: str) -> str:
    """Extracts only alphanumeric characters from a string and converts to lowercase for robust comparison."""
    if not s:
        return ""
    # Remove everything except a-z, A-Z, 0-9 and convert to lower
    return re.sub(r'[^a-zA-Z0-9]', '', str(s)).lower()

def parse_date_val(d_str: str) -> str:
    """
    Normalizes date strings for comparison. 
    Examples: '2021年2月' -> '202102', '2021-02' -> '202102'
    """
    if not d_str:
        return ""
    
    # 連続する数字を抽出 (年、月、日の順を想定)
    nums = re.findall(r'\d+', str(d_str))
    
    if len(nums) >= 2:
        year = nums[0]
        month = nums[1].zfill(2) # 0埋め
        return f"{year}{month}"
    elif len(nums) == 1:
        # 年だけの場合
        return nums[0]
    else:
        return extract_alphanumeric(d_str)

def is_similar_model(m1: str, m2: str) -> bool:
    """
    Checks if two model strings are substantially similar.
    Considers them similar if the alphanumeric string of one is entirely contained in the other.
    e.g., 'dynabookg83hs7n11' and 'g83hs7n11' -> True
    """
    am1 = extract_alphanumeric(m1)
    am2 = extract_alphanumeric(m2)
    
    if not am1 and not am2:
        return True
    if not am1 or not am2:
        return False
        
    return am1 in am2 or am2 in am1

def save_agent_log(query, steps):
    """Saves the agent's scratchpad (intermediate steps) to the database."""
    if not steps:
        return
        
    log_content = []
    for action, observation in steps:
        # Check if action is a list (some agents return list of actions)
        if isinstance(action, list):
            for a in action:
                log_content.append(f"Tool: {a.tool}")
                log_content.append(f"Input: {a.tool_input}")
                log_content.append(f"Log: {a.log}")
        else:
            log_content.append(f"Tool: {action.tool}")
            log_content.append(f"Input: {action.tool_input}")
            log_content.append(f"Log: {action.log}")
            
        log_content.append(f"Observation: {observation}")
        log_content.append("-" * 20)
    
    scratchpad_text = "\n".join(log_content)
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO agent_logs (query, scratchpad) VALUES (?, ?)", (query, scratchpad_text))
        conn.commit()
        conn.close()
        print(f"  [Log saved to database]")
    except Exception as e:
        print(f"Error saving log: {e}")

def get_all_agent_logs():
    """Fetches all agent logs from the database."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT query, scratchpad FROM agent_logs ORDER BY timestamp DESC")
        rows = cursor.fetchall()
        conn.close()
        
        logs = []
        for r in rows:
            logs.append(f"Query: {r[0]}\nLog:\n{r[1]}\n")
        return "\n".join(logs)
    except Exception as e:
        print(f"Error fetching logs: {e}")
        return ""

def send_email_notification(subject: str, body: str):
    """Sends an email notification."""
    smtp_server = os.getenv("EMAIL_SMTP_SERVER")
    smtp_port = os.getenv("EMAIL_SMTP_PORT")
    sender_email = os.getenv("EMAIL_SENDER_ADDRESS")
    sender_password = os.getenv("EMAIL_SENDER_PASSWORD")
    receiver_email = os.getenv("EMAIL_RECEIVER_ADDRESS")

    if not all([smtp_server, smtp_port, sender_email, receiver_email]):
        print("Email configuration missing (Server, Port, Sender, Receiver). Skipping notification.")
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(smtp_server, int(smtp_port))
        server.starttls()
        
        # Only login if password is provided
        if sender_password:
            server.login(sender_email, sender_password)
            
        server.send_message(msg)
        server.quit()
        print(f"Email notification sent: {subject}")
    except Exception as e:
        print(f"Failed to send email: {e}")

# --- Tool Definitions ---

class SaveProductInput(BaseModel):
    name: str = Field(description="Name of the product")
    store: str = Field(description="Name of the store selling the product")
    price: str = Field(description="Price of the product")
    url: Optional[str] = Field(description="URL of the product page", default="")
    description: Optional[str] = Field(description="Brief description of the product", default="")
    model_number: Optional[str] = Field(description="Model number (型番) of the product", default="")
    release_date: Optional[str] = Field(description="Release date (発売日) of the product", default="")
    ram: Optional[str] = Field(description="RAM size", default="")
    ssd: Optional[str] = Field(description="SSD size", default="")

    @model_validator(mode='before')
    @classmethod
    def parse_json_input(cls, data: Any) -> Any:
        if isinstance(data, dict):
             if 'name' in data and ('store' not in data or 'price' not in data):
                name_val = data['name']
                if isinstance(name_val, str) and name_val.strip().startswith('{') and name_val.strip().endswith('}'):
                    try:
                        parsed = json.loads(name_val)
                        if isinstance(parsed, dict):
                            data = parsed
                    except json.JSONDecodeError:
                        pass
        
        if isinstance(data, dict) and 'price' in data:
            if isinstance(data['price'], (int, float)):
                data['price'] = str(data['price'])
                
        return data

class SaveProductTool(BaseTool):
    name = "save_product"
    description = "Saves product information (name, store, price, url, description, model_number, release_date, ram, ssd) to the database."
    args_schema: Type[BaseModel] = SaveProductInput

    def _run(self, name: str, store: str = None, price: str = None, url: str = "", description: str = "", model_number: str = "", release_date: str = "", ram: str = "", ssd: str = "", **kwargs):
        try:
            # Attempt to extract data if 'name' is a dictionary or a JSON string
            parsed_data = {}
            if isinstance(name, dict):
                parsed_data = name
            elif isinstance(name, str) and name.strip().startswith('{') and name.strip().endswith('}'):
                try:
                    parsed_data = json.loads(name)
                except json.JSONDecodeError:
                    pass

            if parsed_data:
                if 'name' in parsed_data:
                    name = parsed_data['name']
                if store is None:
                    store = parsed_data.get('store')
                if price is None:
                    price = parsed_data.get('price')
                if not url:
                    url = parsed_data.get('url', "")
                if not description:
                    description = parsed_data.get('description', "")
                if not model_number:
                    model_number = parsed_data.get('model_number', "")
                if not release_date:
                    release_date = parsed_data.get('release_date', "")
                if not ram:
                    ram = parsed_data.get('ram', "")
                if not ssd:
                    ssd = parsed_data.get('ssd', "")

            if store is None:
                store = kwargs.get('store')
            if price is None:
                price = kwargs.get('price')
            if not model_number:
                model_number = kwargs.get('model_number', "")
            if not release_date:
                release_date = kwargs.get('release_date', "")
            if not ram:
                ram = kwargs.get('ram', "")
            if not ssd:
                ssd = kwargs.get('ssd', "")

            if not name or not store or not price:
                 return f"Error: Required arguments missing. Name: {name}, Store: {store}, Price: {price}"

            # Validate URL and Description presence
            if not url or not description:
                return f"Skipped saving product '{name}': URL or description is missing. URL: '{url}', Description: '{description}'"

            # Validate URL format (must start with http or https)
            if not url.startswith('http://') and not url.startswith('https://'):
                return f"Skipped saving product '{name}': URL must start with 'http://' or 'https://'. URL: '{url}'"

            if isinstance(price, (int, float)):
                price = str(price)
            
            price_val = parse_price_val(price)
            
            if price_val == float('inf'):
                 # Check if it has any digit
                 if not re.search(r'\d', str(price)):
                    return f"Skipped saving product '{name}': Price info is missing or invalid ('{price}')."

            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            # Fetch all existing records for this product name
            cursor.execute("SELECT id, store, price, url FROM products WHERE name = ?", (name,))
            rows = cursor.fetchall()
            
            items = []
            for r in rows:
                items.append({
                    'id': r[0],
                    'store': r[1],
                    'price_str': r[2],
                    'price_val': parse_price_val(r[2]),
                    'url': r[3]
                })
            
            new_price_val = parse_price_val(price)
            msg = ""

            # Sort existing items by price (cheapest first)
            items.sort(key=lambda x: x['price_val'])
            
            current_cheapest = items[0] if items else None
            
            should_save = False
            should_update = False
            
            if not current_cheapest:
                # No existing record, save new one
                should_save = True
            else:
                # Compare with current cheapest
                if new_price_val < current_cheapest['price_val']:
                    # New price is cheaper -> Delete all old records and save new one
                    should_save = True
                    # Delete all existing records for this product name
                    cursor.execute("DELETE FROM products WHERE name = ?", (name,))
                    msg_prefix = f"Found cheaper price! Updated {name} from {current_cheapest['store']} ({current_cheapest['price_str']}) to {store} ({price})."
                elif new_price_val == current_cheapest['price_val']:
                    # Same price -> If same store, update info. If different store, maybe keep existing?
                    # Requirement: "Keep cheapest". If prices are equal, we can overwrite if it's the same store (update info),
                    # or if it's a different store, we might keep the existing one to avoid flapping, 
                    # OR we could overwrite if the new one has more info.
                    # Let's say: 
                    # 1. If same store -> Update (URL/Desc might have changed)
                    # 2. If different store -> Keep existing (First come first served for same price)
                    
                    if store == current_cheapest['store']:
                        should_update = True
                        msg_prefix = f"Updated info for {name} at {store}."
                    else:
                         msg = f"Product {name} exists with same price at {current_cheapest['store']}. Keeping existing."
                else:
                    # New price is higher -> Ignore, unless it's the SAME store updating its price (price increase)
                    # If the store is the same as the current cheapest, we must update (price increase)
                    if store == current_cheapest['store']:
                        should_update = True
                        msg_prefix = f"Price increased for {name} at {store}: {current_cheapest['price_str']} -> {price}."
                    else:
                        msg = f"Product {name} exists cheaper at {current_cheapest['store']} ({current_cheapest['price_str']}). Ignoring {store} ({price})."

            if should_save:
                cursor.execute('''
                    INSERT INTO products (name, store, price, url, description, model_number, release_date, ram, ssd, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (name, store, price, url, description, model_number, release_date, ram, ssd))
                if not msg:
                    msg = f"Saved product: {name} from {store} for {price}."
                else:
                    msg = msg_prefix
                
                # Send email notification for new/saved product
                email_subject = f"Product Saved: {name}"
                email_body = f"Action: Saved (New or Cheaper)\n\nName: {name}\nStore: {store}\nPrice: {price}\nURL: {url}\nModel: {model_number}\nRelease: {release_date}\nRAM: {ram}\nSSD: {ssd}\nDescription: {description}\n\nMessage: {msg}"
                send_email_notification(email_subject, email_body)

            if should_update:
                # Check if anything actually changed (URL, Description, or Price string)
                # We already know price_val is same (or higher for same store), but check text representation
                
                # Fetch current full details
                cursor.execute("SELECT price, url, description, model_number, release_date, ram, ssd FROM products WHERE id = ?", (current_cheapest['id'],))
                curr_row = cursor.fetchone()
                curr_price_str = curr_row[0]
                curr_url = curr_row[1]
                curr_desc = curr_row[2]
                curr_model = curr_row[3]
                curr_release = curr_row[4]
                curr_ram = curr_row[5] if len(curr_row) > 5 else ""
                curr_ssd = curr_row[6] if len(curr_row) > 6 else ""
                
                # Handle cases where existing DB has None
                final_model = model_number if model_number else curr_model
                final_release = release_date if release_date else curr_release
                final_ram = ram if ram else curr_ram
                final_ssd = ssd if ssd else curr_ssd
                
                # Logic to update if ANY field changed
                if (price != curr_price_str or url != curr_url or description != curr_desc or 
                    final_model != curr_model or final_release != curr_release or 
                    final_ram != curr_ram or final_ssd != curr_ssd):
                     cursor.execute('''
                        UPDATE products 
                        SET price = ?, url = ?, description = ?, model_number = ?, release_date = ?, ram = ?, ssd = ?, store = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (price, url, description, final_model, final_release, final_ram, final_ssd, store, current_cheapest['id']))
                     if not msg:
                         msg = f"Updated product {name} info."
                     else:
                         msg = msg_prefix
                     
                     # Send email notification for updated product
                     email_subject = f"Product Updated: {name}"
                     email_body = f"Action: Updated Info\n\nName: {name}\nStore: {store}\nPrice: {price}\nURL: {url}\nModel: {final_model}\nRelease: {final_release}\nRAM: {final_ram}\nSSD: {final_ssd}\nDescription: {description}\n\nMessage: {msg}"
                     send_email_notification(email_subject, email_body)
                else:
                     msg = f"No changes for {name} at {store}."

            # Cleanup: Ensure only 1 record exists per product name (Sanity check)
            # This handles cases where multiple records might have existed before
            if should_save or should_update:
                # Re-fetch all to be sure
                cursor.execute("SELECT id, price FROM products WHERE name = ?", (name,))
                rows = cursor.fetchall()
                if len(rows) > 1:
                    # Keep only the one we just touched (or the cheapest)
                    # Since we did DELETE for should_save, this is mostly for should_update cases
                    # or if concurrent writes happened (unlikely here)
                    
                    # Sort by price, then by ID (newer ID usually means newer insert if logic allows)
                    rows_parsed = []
                    for r in rows:
                        rows_parsed.append({'id': r[0], 'val': parse_price_val(r[1])})
                    
                    rows_parsed.sort(key=lambda x: x['val'])
                    winner = rows_parsed[0]
                    
                    # Delete losers
                    for loser in rows_parsed[1:]:
                        cursor.execute("DELETE FROM products WHERE id = ?", (loser['id'],))
                    msg += " (Cleaned up duplicate records)"

            conn.commit()
            conn.close()
            return msg
        except Exception as e:
            return f"Error saving product: {str(e)}"

class UpdatePricesInput(BaseModel):
    query: str = Field(description="Optional query", default="")

class UpdatePricesTool(BaseTool):
    name = "update_prices"
    description = "Accesses the registered URL for each product in the database directly to check stock, price, and specs. Updates info or deletes if unavailable."
    args_schema: Type[BaseModel] = UpdatePricesInput

    def _fetch_page_content(self, url: str) -> (bool, str, str):
        """
        URLにアクセスし、(成功したか, 理由/エラー, HTMLテキスト) を返す
        """
        if not url or not url.startswith('http'):
            return (False, "Invalid URL", "")
            
        try:
            req = urllib.request.Request(
                url, 
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8'
                }
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                html_content = response.read().decode('utf-8', errors='ignore')
                
                # 自動アクセス防止画面（Bot確認）のチェック
                bot_keywords = [
                    "ロボットではありません", "アクセスが制限されています", "キャプチャ", "CAPTCHA", 
                    "Are you a human?", "Please verify you are a human", "Incapsula", "Cloudflare"
                ]
                html_lower = html_content.lower()
                for kw in bot_keywords:
                    if kw.lower() in html_lower:
                        return (False, "Bot Challenge Detected", "")
                
                # 不要なタグを簡易的に除去してテキストを抽出 (Token節約のため)
                # <style>, <script> の中身を削除
                clean_text = re.sub(r'<script.*?>.*?</script>', '', html_content, flags=re.DOTALL|re.IGNORECASE)
                clean_text = re.sub(r'<style.*?>.*?</style>', '', clean_text, flags=re.DOTALL|re.IGNORECASE)
                # 画像のalt属性をテキストとして残す
                clean_text = re.sub(r'<img[^>]+alt="([^"]*)"[^>]*>', r' \1 ', clean_text, flags=re.IGNORECASE)
                clean_text = re.sub(r"<img[^>]+alt='([^']*)'[^>]*>", r' \1 ', clean_text, flags=re.IGNORECASE)
                
                # HTMLタグを消してテキストのみに
                clean_text = re.sub(r'<.*?>', ' ', clean_text)
                # 余分な空白を圧縮
                clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                
                # LLMへの入力制限のため先頭10000文字程度に切り詰める（通常商品情報はこの辺にある）
                if len(clean_text) > 10000:
                    clean_text = clean_text[:10000]
                    
                return (True, "Success", clean_text)
                
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return (False, "404 Not Found", "")
            elif e.code == 410:
                 return (False, "410 Gone", "")
            elif e.code in [500, 502, 503, 504]:
                 return (False, f"Retryable Server Error ({e.code})", "")
            elif e.code == 403:
                 return (False, "403 Forbidden (Possible Bot Block)", "")
            else:
                return (False, f"HTTP Error {e.code}", "")
        except urllib.error.URLError as e:
            return (False, f"URL Error: {e.reason}", "")
        except Exception as e:
            return (False, f"Connection Error: {e}", "")

    def _delete_product(self, product: dict, reason: str):
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM products WHERE id = ?", (product['id'],))
            conn.commit()
            conn.close()
            
            msg = f"Deleted {product['name']} at {product['store']} ({reason})"
            print(f"  {msg}")
            
            email_subject = f"Product Deleted: {product['name']}"
            email_body = f"Action: Deleted (Unavailable/Not Found)\n\nName: {product['name']}\nStore: {product['store']}\nURL: {product['url']}\nReason: {reason}\n\nMessage: {msg}"
            send_email_notification(email_subject, email_body)
            return True
        except Exception as e:
            print(f"  Error deleting product: {e}")
            return False

    def _run(self, query: str = "", **kwargs):
        print("\n--- Starting Price Update (Direct URL Access) ---")
        products = get_all_products()
        if not products:
            return "No products in database to update."
        
        model_name = os.getenv("MODEL_NAME", "gemini-2.0-flash")
        llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)

        updated_count = 0
        deleted_count = 0
        
        for p in products:
            name = p['name']
            store = p['store']
            url = p['url']
            
            print(f"Checking: {name} at {store} (ID: {p['id']})")
            
            if not url:
                print(f"  [Warning] No URL for this product. Skipping.")
                continue
                
            success, access_reason, page_text = self._fetch_page_content(url)
            
            if not success:
                # 明確な「存在しない」エラー(404, 410, Invalid URL)の場合のみ削除
                if "404 Not Found" in access_reason or "410 Gone" in access_reason or "Invalid URL" in access_reason:
                    print(f"  [Info] URL is dead ({access_reason}). Deleting product.")
                    if self._delete_product(p, access_reason):
                        deleted_count += 1
                else:
                    # 503などのリトライ可能なエラーや、Bot検知(403/CAPTCHA)などの場合は削除せずスキップ
                    print(f"  [Warning] Skipping update due to temporary/access error: {access_reason}")
                continue
                
            # アクセスできた場合は、LLMにテキストを渡して判定させる
            prompt = f"""
            以下のテキストは、ある商品のウェブページから抽出した内容です。
            このページの内容を分析し、以下のタスクを行ってください。
            
            対象商品名: {name}
            対象店舗: {store}
            現在の価格: {p['price']}
            
            抽出テキスト:
            {page_text}
            
            タスク:
            1. このページで対象商品が現在も「販売中」かつ「在庫がある」か判定してください。
               ※「販売終了」「お探しのページは見つかりません」「在庫なし」「在庫切れ」「取り扱いできません」「該当の商品がありません」などの明確な記載（テキストや画像の代替テキスト（alt属性）含む）がある場合は is_unavailable を true にしてください。
               ※商品とは無関係な別商品の在庫情報に騙されないでください。
            2. 販売中である場合、最新の「価格」「詳細情報・スペック(description)」「型番(model_number)」「発売日(release_date)」「メモリ容量(ram)」「SSD容量(ssd)」を抽出してください。発売日は数字とハイフンのみの日付にしてください（例: 2023-10-01）。型番は日付ではなくメーカー名やシリーズ名を含む英数字の文字列を抽出してください。もし発売日と混同されるような表記や数字とハイフンのみであれば、型番として抽出しないでください。
               見つからない項目は空文字("")にしてください。
               ※注意: メモリ（RAM）やSSDなどの容量を抽出する際は、「最大〇〇GB」「〇〇GBまで増設可能」といった拡張上限の数値は対象外とし、必ず「標準搭載の容量」を抽出・記載してください。
               ※RAM容量の単位はGBに統一してください（例: 16384MB -> 16GB）。また、RAM容量やSSD容量に複数候補がある場合は、/（スラッシュ）区切りで保存してください（例: 256GB/512GB/1TB）。
               
            JSON形式で返してください。
            出力例:
            {{
                "is_unavailable": false,
                "unavailability_reason": "",
                "price": "10,500円",
                "description": "最新モデル、送料無料",
                "model_number": "ABC-123",
                "release_date": "2023-10-01",
                "ram": "16GB",
                "ssd": "512GB"
            }}
            """
            
            try:
                response = llm.invoke(prompt)
                content = response.content
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                content = content.strip()
                # Invalid \escape を防ぐため、バックスラッシュをエスケープする
                # ただし、すでに正しくエスケープされている \" や \n などは壊さないようにする簡易的な対処
                # json.loads(..., strict=False) を使いつつ、明らかな不正バックスラッシュを置換
                content = re.sub(r'\\(?![/"\\bfnrtu])', r'\\\\', content)

                try:
                    result_data = json.loads(content, strict=False)
                except json.JSONDecodeError as e:
                    print(f"  [Warning] Failed to parse JSON: {e}. Attempting further cleanup.")
                    # 最後の手段として、バックスラッシュを全て消す
                    content = content.replace('\\', '')
                    result_data = json.loads(content, strict=False)
                
                is_unavailable = result_data.get("is_unavailable", False)
                unavailability_reason = result_data.get("unavailability_reason", "ページ内に在庫なし・販売終了の記載あり")
                
                if is_unavailable:
                    print(f"  [Info] LLM determined product is unavailable. Reason: {unavailability_reason}. Deleting product.")
                    if self._delete_product(p, unavailability_reason):
                        deleted_count += 1
                else:
                    # 更新処理
                    new_price = result_data.get("price", "")
                    new_desc = result_data.get("description", "")
                    new_model = result_data.get("model_number", "")
                    new_release = result_data.get("release_date", "")
                    new_ram = result_data.get("ram", "")
                    new_ssd = result_data.get("ssd", "")
                    
                    if not new_price:
                        # 価格が取れない＝おそらく商品ページではない/在庫なしとして扱う場合もあるが、とりあえず今回はスキップ
                        print(f"  [Warning] Could not extract price from page. Skipping update.")
                        continue
                        
                    final_desc = new_desc if new_desc else p['description']
                    final_model = new_model if new_model else p.get('model_number', "")
                    final_release = new_release if new_release else p.get('release_date', "")
                    final_ram = new_ram if new_ram else p.get('ram', "")
                    final_ssd = new_ssd if new_ssd else p.get('ssd', "")
                    
                    # 変更箇所の特定
                    changes = []
                    
                    # 価格は数字のみを抽出して比較する (表記ゆれによる更新を防ぐため)
                    new_price_val = parse_price_val(new_price)
                    old_price_val = parse_price_val(p['price'])
                    
                    if new_price_val != old_price_val:
                        changes.append(f"Price ({p['price']} -> {new_price})")
                    else:
                        # 価格の数値が同じなら、元の文字列のままにして不要な更新を防ぐ
                        new_price = p['price']
                        
                    # スペック情報も英数字のみで比較し、表記ゆれを無視する
                    old_model = p.get('model_number', "")
                    if not is_similar_model(final_model, old_model):
                        changes.append(f"Model ({old_model} -> {final_model})")
                    else:
                        # 包含関係があれば元のデータを正として維持する（不要な更新を防ぐ）
                        # ただし、新しい方が情報が多い（長い）場合は新しい方を採用するアプローチもあるが、
                        # 今回は「更新なし」と見なすため既存の値を保持する
                        final_model = old_model

                    old_release = p.get('release_date', "")
                    if parse_date_val(final_release) != parse_date_val(old_release):
                        changes.append(f"Release Date ({old_release} -> {final_release})")
                    else:
                        final_release = old_release

                    old_ram = p.get('ram', "")
                    if extract_alphanumeric(final_ram) != extract_alphanumeric(old_ram):
                        changes.append(f"RAM ({old_ram} -> {final_ram})")
                    else:
                        final_ram = old_ram

                    old_ssd = p.get('ssd', "")
                    if extract_alphanumeric(final_ssd) != extract_alphanumeric(old_ssd):
                        changes.append(f"SSD ({old_ssd} -> {final_ssd})")
                    else:
                        final_ssd = old_ssd
                        
                    # 詳細情報の変更はトリガーとして扱わないが、他の項目が更新されたらついでに上書きする
                    # if final_desc != p['description']: ...
                        
                    if changes:
                        try:
                            conn = sqlite3.connect(DB_NAME)
                            cursor = conn.cursor()
                            cursor.execute('''
                                UPDATE products 
                                SET price = ?, description = ?, model_number = ?, release_date = ?, ram = ?, ssd = ?, updated_at = CURRENT_TIMESTAMP
                                WHERE id = ?
                            ''', (new_price, final_desc, final_model, final_release, final_ram, final_ssd, p['id']))
                            conn.commit()
                            
                            if cursor.rowcount > 0:
                                updated_count += 1
                                changes_str = ", ".join(changes)
                                msg = f"Updated {name} at {store}. Changes: {changes_str}"
                                print(f"  {msg}")
                                
                                email_subject = f"Product Updated: {name}"
                                email_body = f"Action: Updated Info (Direct URL Check)\n\nName: {name}\nStore: {store}\nURL: {url}\n\nChanged Fields:\n{changes_str}\n\n--- Current Data ---\nPrice: {new_price}\nModel: {final_model}\nRelease: {final_release}\nRAM: {final_ram}\nSSD: {final_ssd}\nDescription: {final_desc}\n\nMessage: {msg}"
                                send_email_notification(email_subject, email_body)
                            conn.close()
                        except Exception as e:
                            print(f"  Error updating {name} at {store}: {e}")
                    else:
                        print(f"  No spec/price changes for {name} at {store}.")

            except Exception as e:
                print(f"  Error processing LLM response for {name}: {e}")
                
            time.sleep(1) # API/Webへの負荷軽減

        return f"Price update complete. Updated {updated_count} items, Deleted {deleted_count} unavailable items."

class SearchProductsInput(BaseModel):
    query: str = Field(description="Natural language query to search products in the database")

class SearchProductsTool(BaseTool):
    name = "search_products"
    description = "Searches for products in the database using natural language queries (e.g., 'cheapest products', 'items with 16GB memory')."
    args_schema: Type[BaseModel] = SearchProductsInput

    def _run(self, query: str, **kwargs):
        print(f"\n--- Searching Database: {query} ---")
        
        # 1. Use LLM to understand intent
        model_name = os.getenv("MODEL_NAME", "gemini-2.0-flash")
        llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
        
        prompt = f"""
        Analyze the user's search query for products and extract search criteria.
        
        User Query: {query}
        
        Return a JSON object with the following keys:
        - keyword_groups: List of LISTS of keywords. Each inner list represents synonyms (OR condition), and all outer lists must be satisfied (AND condition).
          - Example for "Cheap Mouse": [["mouse", "マウス"]] (Price is handled by sort_by)
          - Example for "16GB Memory": [["16GB", "16G", "16ギガ"], ["memory", "メモリ"]] -> "memory" is often redundant if "16GB" is unique, so prefer specific specs.
          - Example for "32GB PC": [["32GB", "32G"], ["PC", "パソコン", "computer"]]
        - exclude_keywords: List of keywords that MUST NOT appear in the product info (name, description, url).
          - Example for "No SSD": ["SSD"]
          - Example for "exclude memory info": ["memory", "メモリ"]
        - empty_fields: List of field names that must be empty or null (e.g. for "no description", "desc is empty", "url not set").
          - Valid values: "name", "price", "store", "url", "description"
        - sort_by: "price_asc" (cheapest), "price_desc" (expensive), or null (relevance)
        - max_price: integer or null
        - min_price: integer or null
        
        Important Rules for Keywords extraction:
        1. Exclude Metadata Field Names: NEVER include words that refer to database columns like "URL", "url", "price", "name", "title", "description", "store" in `keyword_groups`.
           - CORRECT: "URL with example" -> [["example"]]
           - WRONG: "URL with example" -> [["URL"], ["example"]]
           - CORRECT: "URLにexampleが含まれる" -> [["example"]]
        2. Exclude Action Verbs: Do not include "search", "find", "探して", "検索", "教えて".
        3. Exclude General Terms: Do not include "product", "item", "thing", "もの", "商品".
        4. If the query implies a category (e.g. "PC"), include it as a keyword group.
        
        Example JSON:
        {{
            "keyword_groups": [["mouse", "マウス"]],
            "exclude_keywords": [],
            "empty_fields": [],
            "sort_by": "price_asc",
            "max_price": 5000,
            "min_price": null
        }}
        """
        
        try:
            response = llm.invoke(prompt)
            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            criteria = json.loads(content)
            print(f"  Search Criteria: {criteria}")
            
            # 2. Fetch all products and filter in Python
            all_products = get_all_products()
            filtered_products = []
            
            keyword_groups = criteria.get('keyword_groups', [])
            exclude_keywords = criteria.get('exclude_keywords', [])
            empty_fields = criteria.get('empty_fields', [])
            sort_by = criteria.get('sort_by')
            max_p = criteria.get('max_price')
            min_p = criteria.get('min_price')
            
            for p in all_products:
                text_to_search = (p['name'] + " " + (p['description'] or "") + " " + (p['url'] or "")).lower()
                
                # 2.0 Empty Field Filter
                if empty_fields:
                    is_empty_match = True
                    for field in empty_fields:
                        val = p.get(field)
                        if val and str(val).strip(): # if value exists and is not empty
                            is_empty_match = False
                            break
                    if not is_empty_match:
                        continue

                # 2.0 Exclude Filter
                if exclude_keywords:
                    should_exclude = False
                    for k in exclude_keywords:
                        if k.lower() in text_to_search:
                            should_exclude = True
                            break
                    if should_exclude:
                        continue

                # 2.1 Keyword Match (AND of ORs logic)
                if keyword_groups:
                    all_groups_match = True
                    for group in keyword_groups:
                        # Check if ANY keyword in this group matches (OR)
                        group_match = False
                        for k in group:
                            if k.lower() in text_to_search:
                                group_match = True
                                break
                        if not group_match:
                            all_groups_match = False
                            break
                    
                    if not all_groups_match:
                        continue
                
                # 2.2 Price Filter
                price_val = parse_price_val(p['price'])
                if max_p is not None and price_val > max_p:
                    continue
                if min_p is not None and price_val < min_p:
                    continue
                    
                # Add price_val for sorting
                p['price_val'] = price_val
                filtered_products.append(p)
            
            # 3. Sort
            if sort_by == "price_asc":
                filtered_products.sort(key=lambda x: x['price_val'])
            elif sort_by == "price_desc":
                filtered_products.sort(key=lambda x: x['price_val'], reverse=True)
            
            if not filtered_products:
                return "No products found matching your criteria."
            
            # 4. Format Results
            result_str = f"Found {len(filtered_products)} products:\n"
            # Limit results
            for p in filtered_products[:10]:
                result_str += f"- [ID: {p['id']}] {p['name']} ({p['price']}) @ {p['store']}\n"
                if p['description']:
                    result_str += f"  Desc: {p['description'][:100]}...\n"
                if p['url']:
                    result_str += f"  URL: {p['url']}\n"
                result_str += "\n"
                
            return result_str

        except Exception as e:
            return f"Error executing search: {e}"

class FindSimilarProductsInput(BaseModel):
    query: str = Field(description="Optional query", default="")

class FindSimilarProductsTool(BaseTool):
    name = "find_similar_products"
    description = "Searches for similar products to those in the database and adds the best ones if found."
    args_schema: Type[BaseModel] = FindSimilarProductsInput
    agent_logs: str = ""

    def _run(self, query: str = "", **kwargs):
        print("\n--- Starting Similar Product Search ---")
        products = get_all_products()
        if not products:
            return "No products in database to base search on."
        
        # Filter products based on query if provided
        target_products = []
        if query:
            print(f"Filtering products with query: {query}")
            query_lower = query.lower()
            for p in products:
                if query_lower in p['name'].lower() or \
                   (p['description'] and query_lower in p['description'].lower()):
                    target_products.append(p)
        else:
            target_products = products

        if not target_products:
             return f"No products found matching query '{query}'."

        # Deduplicate by name but keep product data
        unique_products = {}
        for p in target_products:
            if p['name'] not in unique_products:
                unique_products[p['name']] = p
        
        target_names = list(unique_products.keys())
        print(f"Found {len(target_names)} target products to find similar items for.")

        # Use the pre-loaded logs if available
        logs_context = ""
        if self.agent_logs:
            logs_context = f"\n参考情報 (過去の検索履歴):\n{self.agent_logs}\n"

        search = get_search_tool_func()
        model_name = os.getenv("MODEL_NAME", "gemini-2.0-flash")
        llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
        save_tool = SaveProductTool()
        
        cached_similar_items = []
        
        # Limit to avoid too many API calls if many products matched
        max_targets = 5
        if len(target_names) > max_targets:
            print(f"Limiting search to first {max_targets} products.")
            target_names = target_names[:max_targets]

        for name in target_names:
            product_data = unique_products[name]
            description = product_data.get('description', '')
            
            print(f"Searching for similar items to: {name}")
            search_query = f"{name} 類似商品 おすすめ 比較 スペック"
            try:
                search_results = search.run(search_query)
            except Exception as e:
                print(f"Search failed for {name}: {e}")
                continue
            
            prompt = f"""
            以下の検索結果に基づいて、"{name}" に類似した、または競合する製品を抽出してください。
            データベースに既に存在する "{name}" は除外してください。

            【重要】選定基準：
            基準となる商品情報:
            名前: {name}
            詳細: {description}

            上記の基準商品と比較して、「スペック（CPU、メモリ、ストレージ、機能など）が同等かそれ以上」の製品のみを厳選してください。
            基準商品より明らかにスペックが劣る製品（例: 古い世代のCPU、少ないメモリ、低い解像度など）は絶対に含めないでください。
            価格が安くてもスペックが低いものは除外します。
            
            {logs_context}
            検索結果:
            {search_results}
            
            タスク:
            条件に合う製品の 名前、価格、販売店舗、URL、簡単な説明、型番(model_number)、発売日(release_date) を抽出してJSONリストで返してください。型番や発売日が不明な場合は空文字列にしてください。
            
            重要: 
            - URLと詳細情報は必須です。URLは必ず http または https で始まる有効なものにしてください。これらが見つからない、または取得できない場合は、その商品はスキップしてください。
            - 価格が不明な場合、または商品名や価格に（例）などと記載されている場合もスキップしてください。
            - 【必須条件】検索結果のスニペットやページ内に「販売終了」「お探しのページは見つかりません」「404 Not Found」「この商品は現在お取り扱いできません」のいずれかが含まれている場合は、その商品は「無効」とみなし、絶対にリストに含めないでください（スキップしてください）。
            - メモリ（RAM）やSSDなどの容量を説明に含める際、「最大〇〇GB」「〇〇GBまで増設可能」といった拡張上限の数値は対象外とし、必ず「標準搭載の容量」を抽出してください。
            
            JSON出力例:
            [
                {{
                    "name": "競合商品A",
                    "store": "Amazon",
                    "price": "5,000円",
                    "url": "https://www.amazon.co.jp/...",
                    "description": "商品Aの類似品。機能X搭載。",
                    "model_number": "XYZ-999",
                    "release_date": "2024-01-15"
                }}
            ]
            """
            
            try:
                response = llm.invoke(prompt)
                content = response.content
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                items = json.loads(content)
                if isinstance(items, list):
                    for item in items:
                        # Avoid adding the original product itself
                        if item.get('name') == name:
                            continue
                        cached_similar_items.append(item)
                        print(f"  Cached: {item.get('name')} ({item.get('price')})")
            
            except Exception as e:
                print(f"Error processing similar items for {name}: {e}")
            
            time.sleep(1)

        if not cached_similar_items:
            return "No similar products found."

        print(f"\nCached {len(cached_similar_items)} items. Selecting top 3 recommendations...")

        # Select top 3 recommendations from cache
        selection_prompt = f"""
        以下の類似商品リストから、最もおすすめの製品を最大3つ選んでください。
        選定基準: 
        1. 元の商品と同等かそれ以上の性能・品質であること。
        2. 価格と性能のバランスが良いこと。
        3. 詳細情報が豊富であること。
        
        {logs_context}

        候補リスト:
        {json.dumps(cached_similar_items, ensure_ascii=False, indent=2)}
        
        タスク:
        選定した3つの商品をJSONリスト形式で返してください。形式は入力と同じです。
        """
        
        added_count = 0
        try:
            response = llm.invoke(selection_prompt)
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            top_picks = json.loads(content)
            
            if isinstance(top_picks, list):
                for item in top_picks:
                    print(f"  Saving recommendation: {item.get('name')}")
                    res = save_tool._run(
                        name=item.get('name'), 
                        store=item.get('store', 'Unknown'), 
                        price=item.get('price'), 
                        url=item.get('url', ''),
                        description=item.get('description', ''),
                        model_number=item.get('model_number', ''),
                        release_date=item.get('release_date', '')
                    )
                    print(f"  -> {res}")
                    added_count += 1
        except Exception as e:
            return f"Error selecting top recommendations: {e}"

        return f"Similar product search complete. Added {added_count} recommended items."

class CompareProductsInput(BaseModel):
    query: str = Field(description="Optional category or query to filter products for comparison (e.g., 'laptop', 'monitor').", default="")

class CompareProductsTool(BaseTool):
    name = "compare_products"
    description = "Generates a comparison table of products (e.g. RAM, SSD, Price) and ranks them by recommendation. Saves the result as JSON."
    args_schema: Type[BaseModel] = CompareProductsInput

    def _run(self, query: str = "", **kwargs):
        print(f"\n--- Generating Product Comparison: {query} ---")
        
        products = get_all_products()
        if not products:
            return "No products found in database."

        # Filter if query is provided
        target_products = []
        if query:
            query_lower = query.lower()
            for p in products:
                text = (p['name'] + " " + (p['description'] or "")).lower()
                if query_lower in text:
                    target_products.append(p)
        else:
            target_products = products
        
        if not target_products:
            return f"No products found matching '{query}'."

        # 出力トークン切れを防ぐため、チャンクサイズを小さくする
        CHUNK_SIZE = 5
        print(f"Step 1: Extracting specs from {len(target_products)} products in chunks of {CHUNK_SIZE}...")

        model_name = os.getenv("MODEL_NAME", "gemini-2.0-flash")
        llm = ChatGoogleGenerativeAI(model=model_name, temperature=0, max_output_tokens=8192)

        extracted_specs = []

        try:
            for i in range(0, len(target_products), CHUNK_SIZE):
                chunk = target_products[i:i + CHUNK_SIZE]
                print(f"  Processing chunk {i//CHUNK_SIZE + 1} ({len(chunk)} items)...")
                
                # Build prompt for LLM to extract specs only
                prompt_extract = f"""
                以下の製品リストから、各製品の主要スペック情報を抽出してください。

                製品リスト:
                {json.dumps([{k: v for k, v in p.items() if k != 'updated_at'} for p in chunk], ensure_ascii=False, indent=2)}

                タスク:
                各製品について以下の情報を抽出し、JSONリスト形式で出力してください：
                1. id: 元の製品ID (必須)
                2. name: 製品名
                3. price: 価格 (そのまま)
                4. url: 製品ページのURL
                5. ram: メモリ容量 (例: "16GB", "8GB", 不明なら "-") ※「最大〇〇GB」「増設可能」は無視し、標準搭載量のみを抽出すること。
                6. ssd: ストレージ容量 (例: "512GB", "1TB", 不明なら "-") ※「最大〇〇GB」「増設可能」は無視し、標準搭載量のみを抽出すること。
                7. cpu: プロセッサ (例: "Core i5", "M2", 不明なら "-")
                8. os: OSの種類 (例: "Windows 11", "macOS", "ChromeOS", 不明なら "-")
                9. model_number: 型番 (不明なら "-")
                10. release_date: 発売日 (不明なら "-")

                出力はJSONのみとし、Markdownコードブロックで囲ってください。
                """

                response = llm.invoke(prompt_extract)
                content = response.content
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                content = content.strip()
                try:
                    chunk_data = json.loads(content)
                except json.JSONDecodeError as e:
                    print(f"    [Warning] Failed to parse JSON in chunk {i//CHUNK_SIZE + 1}. Attempting aggressive recovery.")
                    print(f"    Error detail: {e}")
                    
                    # 途中で切れている場合の強引な復旧処理
                    try:
                        start_idx = content.find('[')
                        if start_idx != -1:
                            clean_content = content[start_idx:]
                            # もし配列が閉じていなければ閉じる
                            if not clean_content.rstrip().endswith(']'):
                                # 最後の完全なオブジェクト '}' まで探す
                                last_brace = clean_content.rfind('}')
                                if last_brace != -1:
                                    clean_content = clean_content[:last_brace+1] + ']'
                                else:
                                    clean_content += ']'
                            
                            chunk_data = json.loads(clean_content)
                        else:
                            raise ValueError("No JSON list found.")
                    except Exception as e2:
                        print(f"    [Error] Could not recover JSON even after aggressive repair: {e2}")
                        # さらに単純にパースできそうな部分だけを抽出する最終手段 (正規表現)
                        # JSONを直すより、チャンクをスキップして進める方が安全
                        continue

                if isinstance(chunk_data, list):
                    extracted_specs.extend(chunk_data)
                
                time.sleep(1) # API制限配慮
                
            print(f"Step 2: Ranking {len(extracted_specs)} products based on extracted specs...")
            
            # 抽出された全スペック情報から、全体での比較とランキング付けを行う
            # 出力トークン削減のため、元の情報を再出力せず「id, rank, note」のみを要求する
            prompt_rank = f"""
            以下の製品の主要スペック一覧を分析し、価格と性能のバランスに基づいて全体の中からランキングを付けてください。
            
            製品スペックリスト:
            {json.dumps(extracted_specs, ensure_ascii=False, indent=2)}

            タスク:
            各製品に対して、以下の3つの情報のみを含むJSONリスト形式で出力してください：
            1. id: 元の製品ID (必須)
            2. note: 詳細なコメント (推奨理由、メリット・デメリット、他の製品と比較した際の特徴などを具体的に記述してください。例: "同価格帯の中で最もCPU性能が高く、動画編集に適している", "価格は安いがメモリが少ないため、軽作業向け")
            3. rank: 全体の中での「おすすめ順位」 (1から始まる連番)

            重要: 出力トークンを節約するため、nameやprice, url, specs(ram/ssd/cpu/os)等の再出力は絶対にしないでください。「id」「note」「rank」の3つだけを出力してください。

            出力はJSONのみとし、Markdownコードブロックで囲ってください。
            リストの並び順は、rank（1位から順番）にしてください。
            """

            response_rank = llm.invoke(prompt_rank)
            content_rank = response_rank.content
            if "```json" in content_rank:
                content_rank = content_rank.split("```json")[1].split("```")[0]
            elif "```" in content_rank:
                content_rank = content_rank.split("```")[1].split("```")[0]
            
            content_rank = content_rank.strip()
            try:
                ranking_data = json.loads(content_rank)
            except json.JSONDecodeError as e:
                print(f"    [Warning] Failed to parse ranking JSON. Error: {e}. Attempting recovery.")
                start_idx = content_rank.find('[')
                if start_idx != -1:
                    clean_content = content_rank[start_idx:]
                    if not clean_content.rstrip().endswith(']'):
                        last_brace = clean_content.rfind('}')
                        if last_brace != -1:
                            clean_content = clean_content[:last_brace+1] + ']'
                        else:
                            clean_content += ']'
                    try:
                        ranking_data = json.loads(clean_content)
                    except Exception as e2:
                         print(f"    [Error] Could not recover ranking JSON: {e2}")
                         return "Error generating comparison: Invalid JSON format returned by LLM."
                else:
                    return "Error generating comparison: Invalid JSON format returned by LLM."
            
            # Python側でマージする
            spec_dict = {item['id']: item for item in extracted_specs}
            target_dict = {item['id']: item for item in target_products}
            final_comparison_data = []
            
            for rank_item in ranking_data:
                p_id = rank_item.get('id')
                if p_id in spec_dict:
                    merged = spec_dict[p_id].copy()
                    merged['rank'] = rank_item.get('rank')
                    merged['note'] = rank_item.get('note', '')
                    if p_id in target_dict:
                        merged['updated_at'] = target_dict[p_id].get('updated_at', '')
                    final_comparison_data.append(merged)
            
            # ランクでソートしておく（念のため）
            final_comparison_data.sort(key=lambda x: x.get('rank', 9999))
            
            # 型番や発売日を追加したことで None が入る可能性があるので、None を空文字に変換
            for item in final_comparison_data:
                if 'model_number' not in item or item['model_number'] is None:
                    item['model_number'] = ""
                if 'release_date' not in item or item['release_date'] is None:
                    item['release_date'] = ""

            # Save to file
            from datetime import datetime
            output_data = {
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "products": final_comparison_data
            }
            output_file = "product_comparison.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            return f"Comparison table generated and saved to {output_file}. Included {len(final_comparison_data)} ranked items."

        except Exception as e:
            return f"Error generating comparison: {e}"

# --- Agent Setup ---

def display_products():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, store, price FROM products")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("\nNo products saved yet.")
        return

    def parse_price_sort(p_str):
        nums = re.findall(r'\d+', str(p_str).replace(',', ''))
        return int(''.join(nums)) if nums else float('inf')

    rows.sort(key=lambda x: (x[1], parse_price_sort(x[3])))
    
    print("\n--- All Saved Products ---")
    print(f"{'ID':<5} {'Name':<40} {'Store':<20} {'Price':<15}")
    print("-" * 85)
    for row in rows:
        name_disp = (row[1][:37] + '..') if len(row[1]) > 39 else row[1]
        store_disp = (row[2][:18] + '..') if len(row[2]) > 20 else row[2]
        print(f"{row[0]:<5} {name_disp:<40} {store_disp:<20} {row[3]:<15}")
    print("-" * 85)

def show_product_details(product_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, store, price, url, description, model_number, release_date FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        print(f"\nProduct with ID {product_id} not found.")
        return

    print("\n--- Product Details ---")
    print(f"ID:          {row[0]}")
    print(f"Name:        {row[1]}")
    print(f"Store:       {row[2]}")
    print(f"Price:       {row[3]}")
    print(f"Model:       {row[6] if len(row)>6 else ''}")
    print(f"Release:     {row[7] if len(row)>7 else ''}")
    print(f"URL:         {row[4]}")
    print(f"Description: {row[5]}")
    print("-" * 30)

def delete_product_records(identifiers: List[str]):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    deleted_count = 0
    errors = []
    
    print(f"\nAttempting to delete: {identifiers}")

    for identifier in identifiers:
        try:
            # Check if identifier is an ID (digit)
            if identifier.isdigit():
                cursor.execute("DELETE FROM products WHERE id = ?", (int(identifier),))
            else:
                # Treat as Name
                cursor.execute("DELETE FROM products WHERE name = ?", (identifier,))
                
            if cursor.rowcount > 0:
                deleted_count += cursor.rowcount
                print(f"  Deleted: {identifier}")
            else:
                errors.append(f"No product found with ID/Name: {identifier}")
        except Exception as e:
            errors.append(f"Error deleting {identifier}: {e}")

    conn.commit()
    conn.close()
    
    print(f"\nTotal deleted: {deleted_count}")
    if errors:
        print("Errors/Warnings:")
        for err in errors:
            print(f"  - {err}")

def main():
    if not os.getenv("GOOGLE_API_KEY"):
        print("Error: GOOGLE_API_KEY not found.")
        return
    
    provider = os.getenv("SEARCH_PROVIDER", "serpapi")
    if provider == "serpapi" and not os.getenv("SERPAPI_API_KEY"):
        print("Error: SERPAPI_API_KEY not found.")
        return
    elif provider == "tavily_api" and not os.getenv("TAVILY_API_KEY"):
        print("Error: TAVILY_API_KEY not found for Tavily search.")
        return
    elif provider == "browser_use":
        # Browser Use only needs GOOGLE_API_KEY for the LLM, which is checked above.
        pass

    model_name = os.getenv("MODEL_NAME", "gemini-2.0-flash")
    print(f"Using model: {model_name}")
    print(f"Using Search Provider: {provider}")

    llm = ChatGoogleGenerativeAI(model=model_name, temperature=0, max_retries=10)
    
    search = get_search_tool_func()
    search_tool = Tool(
        name="google_search",
        description="Search Google for recent results.",
        func=search.run,
    )
    
    # Load agent logs at startup
    startup_logs = get_all_agent_logs()
    print(f"Loaded {len(startup_logs)} characters of agent logs.")

    save_tool = SaveProductTool()
    db_search_tool = SearchProductsTool()
    update_tool = UpdatePricesTool()
    similar_tool = FindSimilarProductsTool(agent_logs=startup_logs)
    compare_tool = CompareProductsTool()
    
    tools = [search_tool, save_tool, db_search_tool, update_tool, similar_tool, compare_tool]
    
    # Define Prompt with Chat History
    prompt = ChatPromptTemplate.from_messages([
        ("system", """あなたは、商品の検索、保存、価格更新、類似商品検索、比較表作成を行う有能なアシスタントです。
        
        利用可能なツール:
        1. google_search: インターネット上の商品情報の検索に使用します。
        2. save_product: 商品情報をデータベースに保存します。
        3. search_products: データベース内に保存された商品を自然言語で検索します（例：「安いもの」「メモリが多いもの」）。
        4. update_prices: データベース内の全商品の価格を最新の状態に更新します。
        5. find_similar_products: データベース内の商品に類似した商品を探して追加します。
        6. compare_products: データベース内の商品の比較表（RAM, SSD, 価格など）を作成し、おすすめ順に並べます。

        重要: 検索を行って商品が見つかった場合は、必ず `save_product` ツールを使用して、見つかった各商品をデータベースに保存してください。
        保存する際は、商品名、価格、店舗名、詳細、URLを含めてください。
        
        【重要】URLと詳細情報（description）は保存において必須項目です。
        特にURLは `http://` または `https://` で始まる有効な形式である必要があります。
        これらが取得できない場合やURLが無効な場合は、その商品は保存しないでください。
        検索結果から情報を抽出する際は、これらの項目を必ず探してください。
        また、可能であれば「型番（model_number）」と「発売日（release_date）」も抽出・保存してください。

        【無効な商品の保存禁止】
        検索結果のスニペットや実際のページ内に、以下のいずれかの文言が含まれている商品は、現在利用できない無効な商品です。これらは絶対に `save_product` でデータベースに保存しないでください。
        - 「販売終了」
        - 「お探しのページは見つかりません」
        - 「404 Not Found」
        - 「この商品は現在お取り扱いできません」
        
        価格情報が曖昧な場合（例：「10万円以下」）でも、上記の無効条件に該当せず、URLと詳細情報があれば `save_product` を使用して保存してください。
        その際、priceフィールドには見つかったテキスト（例：「10万円以下」）を入力してください。

        ユーザーの指示に従って適切なツールを使用してください。
        「価格を更新して」と言われたら update_prices を使用してください。
        「類似商品を探して」と言われたら find_similar_products を使用してください。
        """),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, return_intermediate_steps=True)
    
    print("Advanced AI Agent initialized.")
    print("Commands: 'list', 'show <ID>', 'update', 'similar', 'delete <ID/Name> ...', 'quit'")
    
    chat_history = []
    
    while True:
        try:
            try:
                user_input = input("\nEnter command or search query: ")
            except EOFError:
                print("\nEOF detected. Exiting...")
                break

            if user_input.lower() in ['quit', 'exit']:
                break
            
            if user_input.lower() == 'list':
                display_products()
                continue
            
            # Direct Command Execution for Update
            if user_input.lower() == 'update':
                result = update_tool._run()
                print(result)
                continue

            # Direct Command Execution for Similar Search
            if user_input.lower() == 'similar':
                result = similar_tool._run()
                print(result)
                continue

            # Direct Command Execution for Comparison
            if user_input.lower().startswith('compare'):
                parts = user_input.split(maxsplit=1)
                query = parts[1] if len(parts) > 1 else ""
                result = compare_tool._run(query)
                print(result)
                continue

            # Direct Command Execution for Search
            if user_input.lower().startswith('search_products '):
                query = user_input[16:].strip()
                if query:
                    result = db_search_tool._run(query)
                    print(result)
                else:
                    print("Usage: search_products <query>")
                continue

            if user_input.lower().startswith('show '):
                parts = user_input.split()
                if len(parts) > 1 and parts[1].isdigit():
                    show_product_details(int(parts[1]))
                else:
                    print("Usage: show <product_id>")
                continue
            
            if user_input.lower().startswith('delete '):
                try:
                    parts = shlex.split(user_input)
                    if len(parts) > 1:
                        identifiers = parts[1:]
                        delete_product_records(identifiers)
                    else:
                        print("Usage: delete <ID/Name> ...")
                except ValueError as e:
                    print(f"Error parsing command: {e}")
                continue

            if user_input:
                print(f"\nProcessing: {user_input}...\n")
                result = agent_executor.invoke({
                    "input": user_input,
                    "chat_history": chat_history
                })
                
                # Update Chat History
                chat_history.append(HumanMessage(content=user_input))
                if isinstance(result["output"], str):
                    chat_history.append(AIMessage(content=result["output"]))
                
                # Save scratchpad logs
                if "intermediate_steps" in result:
                    save_agent_log(user_input, result["intermediate_steps"])
                
                display_products()
                
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
