CREATE TABLE IF NOT EXISTS products (
 product_id TEXT PRIMARY KEY, product_name TEXT NOT NULL, category TEXT NOT NULL,
 updated_at TIMESTAMPTZ NOT NULL, is_deleted BOOLEAN NOT NULL DEFAULT FALSE);
CREATE TABLE IF NOT EXISTS orders (
 order_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, ordered_at TIMESTAMPTZ NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('paid','pending','cancelled')), currency TEXT NOT NULL,
 updated_at TIMESTAMPTZ NOT NULL, is_deleted BOOLEAN NOT NULL DEFAULT FALSE);
CREATE TABLE IF NOT EXISTS order_items (
 order_id TEXT REFERENCES orders, line_id TEXT, product_id TEXT REFERENCES products,
 quantity INTEGER NOT NULL, unit_price NUMERIC(18,2) NOT NULL, discount_amount NUMERIC(18,2) NOT NULL,
 updated_at TIMESTAMPTZ NOT NULL, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
 PRIMARY KEY(order_id,line_id));
CREATE TABLE IF NOT EXISTS payments (
 payment_id TEXT PRIMARY KEY, order_id TEXT REFERENCES orders, amount NUMERIC(18,2) NOT NULL,
 status TEXT NOT NULL, attempted_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
 is_deleted BOOLEAN NOT NULL DEFAULT FALSE);
CREATE INDEX IF NOT EXISTS orders_updated ON orders(updated_at);
CREATE INDEX IF NOT EXISTS items_updated ON order_items(updated_at);
CREATE INDEX IF NOT EXISTS payments_updated ON payments(updated_at);
CREATE INDEX IF NOT EXISTS products_updated ON products(updated_at);
