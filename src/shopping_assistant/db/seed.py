from sqlalchemy import text

from shopping_assistant.db.seed_data import CUSTOMERS, PRODUCTS, REVIEWS
from shopping_assistant.db.session import get_engine

PRODUCT_COLS = ("id", "name", "category", "price", "description", "is_organic")
REVIEW_COLS = ("product_id", "rating", "reviewer_name", "review_text")   # add "id" first if present
CUSTOMER_COLS = ("id", "name", "email", "credit_card_number", "location", "age")


def _dicts(cols, rows):
    return [dict(zip(cols, r, strict=True)) for r in rows]


def seed() -> None:
    products = _dicts(PRODUCT_COLS, PRODUCTS)
    for p in products:
        p["is_organic"] = bool(p["is_organic"])          # SQLite 0/1 -> Postgres boolean
    customers = _dicts(CUSTOMER_COLS, CUSTOMERS)
    for c in customers:
        c["credit_card_number"] = str(c["credit_card_number"])   # INTEGER -> TEXT
    reviews = _dicts(REVIEW_COLS, REVIEWS)

    with get_engine().begin() as conn:          # one transaction: all or nothing
        conn.execute(text(
            "TRUNCATE orders, reviews, customers, products RESTART IDENTITY CASCADE"))

        conn.execute(text(
            "INSERT INTO products (id, name, category, price, description, is_organic) "
            "VALUES (:id, :name, :category, :price, :description, :is_organic)"), products)
        conn.execute(text(
            "INSERT INTO customers (id, name, email, credit_card_number, location, age) "
            "VALUES (:id, :name, :email, :credit_card_number, :location, :age)"), customers)
        conn.execute(text(
            "INSERT INTO reviews (product_id, rating, reviewer_name, review_text) "
            "VALUES (:product_id, :rating, :reviewer_name, :review_text)"), reviews)

        # explicit ids don't advance the sequences, so do it by hand
        for table in ("products", "customers"):
            conn.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                f"(SELECT MAX(id) FROM {table}))"))

    print(f"seeded {len(products)} products, {len(customers)} customers, {len(reviews)} reviews")


if __name__ == "__main__":
    seed()