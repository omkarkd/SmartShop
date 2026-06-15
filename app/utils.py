import duckdb

def search_products(query, min_q=None, max_q=None, unit=None):
    sql = f"""
        SELECT product_name, price, quantity, unit, pack_size
        FROM 'data/products.parquet'
        WHERE LOWER(clean_name) LIKE '%{query.lower()}%'
    """

    if unit:
        sql += f" AND unit = '{unit}'"

    if min_q is not None and max_q is not None:
        sql += f" AND quantity BETWEEN {min_q} AND {max_q}"

    sql += " LIMIT 50"

    return duckdb.sql(sql).df()