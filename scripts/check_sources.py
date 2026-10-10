"""Verify the seeded demo's source counts and independent business arithmetic."""
import os
from decimal import Decimal


def main():
    import psycopg
    from pymongo import MongoClient
    with psycopg.connect(host=os.environ.get('PGHOST','127.0.0.1'), port=os.environ.get('PGPORT','5432'),
                         dbname=os.environ.get('PGDATABASE','ecommerce'), user=os.environ.get('PGUSER','demo'),
                         password=os.environ['POSTGRES_PASSWORD']) as db:
        counts = {}
        for table in ['orders','order_items','payments','products']:
            # Names are fixed in source, never accepted from input.
            counts[table] = db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        sales = db.execute("SELECT SUM(i.quantity*i.unit_price-i.discount_amount) FROM order_items i JOIN orders o USING(order_id) WHERE o.status='paid' AND NOT o.is_deleted AND NOT i.is_deleted").fetchone()[0]
        attempts = db.execute("SELECT COUNT(*) FILTER (WHERE status='SUCCESS'),COUNT(*) FROM payments WHERE NOT is_deleted").fetchone()
        if counts != dict(orders=3,order_items=3,payments=4,products=3) or sales != Decimal('1200.00') or attempts != (2,4):
            raise RuntimeError(f'Source fixture differs from isolated baseline: {counts}, sales={sales}, attempts={attempts}')
    with MongoClient(host=os.environ.get('MONGO_HOST','127.0.0.1'),port=int(os.environ.get('MONGO_PORT','27017')),
                     username=os.environ.get('MONGO_USER','demo'),password=os.environ['MONGO_PASSWORD'],authSource='admin',serverSelectionTimeoutMS=10000) as client:
        collection = client.ecommerce.customers
        if collection.count_documents({}) != 2 or collection.count_documents({'updated_at':{'$type':'date'}}) != 2:
            raise RuntimeError('Customer fixture count or BSON datetime type mismatch')
        customers = list(collection.find({}, {'_id':0,'customer_id':1,'profile.loyalty_tier':1}))
    print({'source_counts':counts,'net_sales':str(sales),'successful_attempts':attempts[0],'all_attempts':attempts[1],'customers':customers})


if __name__ == '__main__':
    main()
