import json
import sqlite3
import re
from pydantic import BaseModel, Field

class SaveProductTool:
    def _run(self, name: str, store: str = None, price: str = None, url: str = "", description: str = "", model_number: str = "", release_date: str = "", ram: str = "", ssd: str = "", **kwargs):
        try:
            if should_save:
                cursor.execute('''
                    INSERT INTO products (name, store, price, url, description, model_number, release_date, ram, ssd, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (name, store, price, url, description, model_number, release_date, ram, ssd))
                if not msg:
                    msg = f"Saved product: {name} from {store} for {price}."
                else:
                    msg = msg_prefix

            if should_update:
                if (price != curr_price_str):
                     cursor.execute('''
                        UPDATE products 
                        SET price = ?, url = ?, description = ?, model_number = ?, release_date = ?, ram = ?, ssd = ?, store = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (price, url, description, final_model, final_release, final_ram, final_ssd, store, current_cheapest['id']))
                     if not msg:
                         msg = f"Updated product {name} info."
                     else:
                         msg = msg_prefix
                else:
                     msg = f"No changes for {name} at {store}."

            if should_save or should_update:
                cursor.execute("SELECT id, price FROM products WHERE name = ?", (name,))
                rows = cursor.fetchall()
                if len(rows) > 1:
                    rows_parsed = []
                    for r in rows:
                        rows_parsed.append({'id': r[0], 'val': parse_price_val(r[1])})
                    
                    rows_parsed.sort(key=lambda x: x['val'])
                    winner = rows_parsed[0]
                    
                    for loser in rows_parsed[1:]:
                        cursor.execute("DELETE FROM products WHERE id = ?", (loser['id'],))
                    msg += " (Cleaned up duplicate records)"

            conn.commit()
            conn.close()
            return msg
        except Exception as e:
            return f"Error saving product: {str(e)}"
