import base64
import json
import os
import sqlite3
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import ToolRuntime, tool
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from reviews_api import get_product_rating

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(__file__), "store.db")


@dataclass
class CustomerContext:
    """Per-session context passed to the agent at invoke time (never chosen by the LLM)."""
    customer_id: int
    customer_name: str


def ensure_schema() -> None:
    """Add orders.customer_id to databases created before that column existed."""
    conn = sqlite3.connect(DB_PATH)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(orders)")]
    if cols and "customer_id" not in cols:
        conn.execute("ALTER TABLE orders ADD COLUMN customer_id INTEGER")
        conn.commit()
    conn.close()


def find_customer(name: str) -> list[tuple[int, str, str]]:
    """Return (id, name, email) for customers whose name matches (case-insensitive, trimmed)."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, name, email FROM customers WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))",
        (name,),
    ).fetchall()
    conn.close()
    return rows


ensure_schema()

llm = ChatOpenAI(model="gpt-5-mini", temperature=0)
vision_llm = ChatOpenAI(model="gpt-5-mini", temperature=0)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def search_products(query: str, max_price: Optional[float] = None, is_organic: Optional[bool] = None) -> str:
    """
    Search the product database by keyword (matched against name, description, and category).
    Optionally filter by maximum price and/or organic status.
    Returns a JSON array of matching products, each with: id, name, category, price,
    description, is_organic.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    sql = "SELECT id, name, category, price, description, is_organic FROM products WHERE 1=1"
    params: list = []

    if query:
        sql += " AND (name LIKE ? OR description LIKE ? OR category LIKE ?)"
        like = f"%{query}%"
        params.extend([like, like, like])

    if max_price is not None:
        sql += " AND price <= ?"
        params.append(max_price)

    if is_organic is not None:
        sql += " AND is_organic = ?"
        params.append(1 if is_organic else 0)

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    products = [
        {
            "id":          row[0],
            "name":        row[1],
            "category":    row[2],
            "price":       row[3],
            "description": row[4],
            "is_organic":  bool(row[5]),
        }
        for row in rows
    ]
    return json.dumps(products)


@tool
def get_rating(product_id: int) -> str:
    """
    Get the average customer rating and total review count for a product by its ID.
    Returns a JSON object with: product_id, average_rating, review_count.
    """
    result = get_product_rating(product_id)
    return json.dumps(result)


@tool
def checkout(product_id: int, runtime: ToolRuntime[CustomerContext]) -> str:
    """
    Place an order for the given product ID on behalf of the logged-in customer.
    Saves the order to the database and returns a confirmation message with the
    order ID, product name, and price.
    """
    customer_id = runtime.context.customer_id
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, price FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return f"Error: product with ID {product_id} not found."

    name, price = row
    cursor.execute(
        "INSERT INTO orders (customer_id, product_id, product_name, price) VALUES (?, ?, ?, ?)",
        (customer_id, product_id, name, price),
    )
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return (
        f"Order #{order_id} confirmed! '{name}' has been successfully ordered for ${price:.2f}. "
        f"Your order will arrive in 3-5 business days. Thank you for shopping with us!"
    )


@tool
def describe_product_image(image_path: str) -> str:
    """
    Analyze a product image and return its key attributes as a JSON object.
    Use this when the user uploads a photo of a product they are interested in.
    The returned attributes can be used directly with search_products.
    """
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()

    ext = os.path.splitext(image_path)[1].lower().lstrip(".")
    mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"

    message = HumanMessage(content=[
        {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{image_data}"},
        },
        {
            "type": "text",
            "text": (
                "Look at this product image and extract its key attributes. "
                "Return ONLY a JSON object with these fields:\n"
                "- product_type: what kind of product it is (e.g. honey, olive oil, almonds)\n"
                "- search_query: a short keyword to search for it (e.g. 'honey', 'olive oil')\n"
                "- is_organic: true if the label says organic, false if not, null if unclear\n"
                "- description: one sentence describing the product"
            ),
        },
    ])

    response = vision_llm.invoke([message])
    return response.content

@tool
def get_orders_history(runtime: ToolRuntime[CustomerContext]) -> str:
    """
    Retrieve the order history of the logged-in customer.
    Returns a JSON array of orders, each with: order_id, product_id, product_name, price, order_date.
    """
    customer_id = runtime.context.customer_id
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, product_id, product_name, price, ordered_at FROM orders "
        "WHERE customer_id = ? ORDER BY ordered_at DESC",
        (customer_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    orders = [
        {
            "order_id":     row[0],
            "product_id":   row[1],
            "product_name": row[2],
            "price":        row[3],
            "order_date":   row[4],
        }
        for row in rows
    ]
    return json.dumps(orders)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = create_agent(
    tools=[search_products, get_rating, checkout, describe_product_image, get_orders_history],
    model=llm,
    context_schema=CustomerContext,
    system_prompt=(
        "You are a helpful shopping assistant. Follow these rules strictly.\n\n"
        "IMAGE SEARCH — when the user provides an image path:\n"
        "1. Call describe_product_image with the path to identify the product.\n"
        "2. Use the returned search_query and is_organic to call search_products.\n"
        "3. Continue with the BROWSING flow from step 2 onwards.\n\n"
        "BROWSING — when the user describes what they want to buy:\n"
        "1. Call search_products to find matching items (apply any price/organic filters given).\n"
        "2. For each candidate, call get_rating to retrieve its average rating.\n"
        "3. Filter by the user's minimum rating if specified.\n"
        "4. Present qualifying products as a numbered list. For each item use this exact format "
        "   (plain text, no backticks, no code blocks, no bold, no italic):\n\n"
        "   #<number>. <name> (ID:<product_id>) — $<price> ★<rating> — <organic or non-organic>\n\n"
        "   Add a blank line between each product entry for readability. "
        "   Always include (ID:X) so you can reference it later.\n"
        "5. If only one product qualifies, still show it in the list and ask: "
        "   'Would you like to order it? Just say yes or give me the number.'\n"
        "6. Do NOT call checkout at this stage.\n\n"
        "ORDERING — when the user confirms they want to buy (e.g. 'yes', 'sure', 'go ahead', "
        "'order number 2', 'the first one', 'get me #3'):\n"
        "1. Look at your previous message to find the (ID:X) for the chosen product "
        "   (if only one was listed and the user says 'yes', use that product's ID).\n"
        "2. Call checkout with that product_id (the number from (ID:X)).\n"
        "3. Confirm the order to the user in plain text.\n\n"
        "Never place an order unless the user explicitly confirms. "
        "Never guess a product_id — always take it from the (ID:X) in your own previous message.\n\n"
        "ORDER HISTORY — when the user asks to see their order history (e.g. 'show my orders', 'what did I buy?'):\n"
        "1. Call get_orders_history (the logged-in customer is identified automatically).\n"
        "2. Present the order history in a clear, organized format.\n"
    ),
)

if __name__ == "__main__":
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "I want to buy organic honey with 4.5+ rating and less than $20 price."
                    ),
                }
            ]
        },
        context=CustomerContext(customer_id=1, customer_name="John Doe"),
    )
    print(result["messages"][-1].content)
