from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_mysqldb import MySQL
import json, sys, os

app = Flask(__name__)

#Get the environment variables
MYSQL_HOST = os.getenv('MYSQL_HOST', '')
MYSQL_USER = os.getenv('MYSQL_USER', '')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
MYSQL_DB = os.getenv('MYSQL_DATABASE', '')
secret_key = os.getenv('SECRET_KEY', '')

#print("Check" + MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB, secret_key)

# Configure database details using environment variables
app.config['MYSQL_HOST'] = MYSQL_HOST
app.config['MYSQL_USER'] = MYSQL_USER
app.config['MYSQL_PASSWORD'] = MYSQL_PASSWORD
app.config['MYSQL_DB'] = MYSQL_DB
app.secret_key = secret_key  # Change to a random secret key

# app.config['MYSQL_HOST'] = MYSQL_HOST
# app.config['MYSQL_USER'] = MYSQL_USER
# app.config['MYSQL_PASSWORD'] = ''
# app.config['MYSQL_DB'] = 'amazon_sales_project'
# app.secret_key = 'advance_database_project'  # Change to a random secret key

mysql = MySQL(app)

# Your homepage '/' now serves as the login page
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Make sure you're getting JSON data correctly
        data = request.get_json()
        username = data['username']
        user_id = data['user_id']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM Users WHERE user_name = %s AND user_id = %s", (username, user_id,))
        user = cur.fetchone()
        cur.close()

        if user:
            session['username'] = username  # Set the username in the session
            return jsonify({'valid': True})
        else:
            return jsonify({'valid': False})

    # If it's a GET request, render the login page
    return render_template('login.html')

@app.route('/register_user', methods=['POST'])
def register_user():
    data = request.get_json()
    username = data.get('username')
    user_id = data.get('user_id')

    if not username or not user_id:
        return jsonify({'registered': False, 'message': 'Missing username or user ID'}), 400

    try:
        with mysql.connection.cursor() as cur:
            # Check if user already exists
            cur.execute("SELECT * FROM Users WHERE user_name = %s OR user_id = %s", (username, user_id))
            if cur.fetchone():
                return jsonify({'registered': False, 'message': 'User already exists'}), 409

            # Insert new user
            cur.execute("INSERT INTO Users (user_name, user_id) VALUES (%s, %s)", (username, user_id))
            mysql.connection.commit()

            # Set the username in the session after successful registration
            session['username'] = username

            return jsonify({'registered': True, 'message': 'Registration successful'})

    except Exception as e:
        print("Error: ", e, file=sys.stderr)  # Print error to stderr
        mysql.connection.rollback()  # Ensure any failed transaction is rolled back
        return jsonify({'registered': False, 'message': 'Database error'}), 500
    
@app.route('/home', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        search_term = request.form['search']
        return redirect(url_for('compare_product', query=search_term))

    cur = mysql.connection.cursor()

    # Fetch trending deals
    cur.execute("""
        SELECT 
            p.product_id AS 'Product ID', 
            p.product_name AS 'Product Name', 
            p.rating AS 'Rating', 
            COUNT(r.review_id) AS 'Total Reviews'
        FROM 
            Products p
        LEFT JOIN 
            Reviews r ON p.product_id = r.product_id
        GROUP BY 
            p.product_id, p.product_name, p.rating
        ORDER BY 
            p.rating DESC, COUNT(r.review_id) DESC;
    """)
    trending_deals = cur.fetchall()
    # Fetch discounts and deals
    discounts_data = discounts_and_deals()  # Pass cursor to function if it requires a database query
    fifty_data = under_fifty()  # Pass cursor to function if it requires a database query
    cur.close()  # Close cursor after all queries

    return render_template('home.html', 
                           trending_deals=trending_deals, 
                           discounts_and_deals=discounts_data, 
                           under_fifty=fifty_data)

@app.route('/autocomplete', methods=['GET'])
def autocomplete():
    search_term = request.args.get('term', '')
    cur = mysql.connection.cursor()
    cur.execute("SELECT product_name FROM Products WHERE product_name LIKE %s LIMIT 5", ('%' + search_term + '%',))
    products = cur.fetchall()
    cur.close()
    # Convert tuple results to a list of product names
    product_list = [product[0] for product in products]
    return jsonify(product_list)

@app.route('/userprofile', methods=['GET', 'POST'])
def user_profile():
    username = session.get('username')
    if not username:
        return redirect(url_for('login'))  # Redirect to login if the user is not logged in

    cur = mysql.connection.cursor()

    # Fetch products for dropdown list
    cur.execute("SELECT product_id, product_name FROM Products")
    products = cur.fetchall()

    if request.method == 'POST':
        # Get form data
        review_id = request.form.get('review_id')  # New line to capture review_id
        product_id = request.form.get('product_id')
        review_title = request.form.get('review_title')
        review_content = request.form.get('review_content')

        # Check if review_id already exists
        cur.execute("SELECT 1 FROM Reviews WHERE review_id = %s", (review_id,))
        if cur.fetchone():
            cur.close()
            return "Review ID already exists", 400

        # Insert new review into the database
        cur.execute("""
            INSERT INTO Reviews (review_id, product_id, user_id, review_title, review_content)
            VALUES (%s, %s, (SELECT user_id FROM Users WHERE user_name = %s), %s, %s)
        """, (review_id, product_id, username, review_title, review_content))
        mysql.connection.commit()

    # Fetch reviews for the current user
    cur.execute("""
        SELECT r.review_id, r.product_id, p.product_name, r.review_title, r.review_content
        FROM Reviews r
        JOIN Products p ON r.product_id = p.product_id
        WHERE r.user_id = (SELECT user_id FROM Users WHERE user_name = %s)
    """, (username,))
    reviews = cur.fetchall()

    cur.close()

    return render_template('userprofile.html', reviews=reviews, username=username, products=products)


@app.route('/delete_review/<review_id>', methods=['POST'])
def delete_review(review_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM Reviews WHERE review_id = %s", (review_id,))
        mysql.connection.commit()
        cur.close()
    except Exception as e:
        print("Error: ", e, file=sys.stderr)
        # You can return a message or redirect as you see fit
        return "An error occurred during deletion", 500

    # Redirect to the user profile page or you can return a success message
    return redirect(url_for('user_profile'))

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'username' not in session:
        return redirect(url_for('login'))

    new_username = request.form.get('newUsername')
    if not new_username:
        return "Username is required.", 400

    try:
        with mysql.connection.cursor() as cur:
            cur.execute("UPDATE Users SET user_name = %s WHERE user_name = %s", (new_username, session['username']))
            mysql.connection.commit()
            session.pop('username', None)  # Log out the user after updating the profile
            return redirect(url_for('login'))
    except Exception as e:
        return f"An error occurred: {e}", 500

@app.route('/user_reviews')
def user_reviews():
    username = session.get('username')
    if not username:
        return redirect(url_for('login'))  # Redirect to login if the user is not logged in

    try:
        cur = mysql.connection.cursor()
        # Fetch user_id based on username to link to the reviews
        cur.execute("SELECT user_id FROM Users WHERE user_name = %s", (username,))
        user_id = cur.fetchone()
        
        if not user_id:
            return "No such user found", 404
        
        # Fetch reviews made by this user
        cur.execute("""
            SELECT r.review_id, r.product_id, r.user_id, r.review_title, r.review_content
            FROM Reviews r
            WHERE r.user_id = %s
        """, (user_id[0],))
        reviews = cur.fetchall()
        
        # Check if products in reviews exist
        reviews_with_products = []
        for review in reviews:
            cur.execute("SELECT product_name FROM Products WHERE product_id = %s", (review[1],))
            product = cur.fetchone()
            if product:
                reviews_with_products.append(review + (product[0],))  # Append product name to the review tuple
        cur.close()
        
        return render_template('user_reviews.html', reviews=reviews_with_products, username=username)
    except Exception as e:
        print("Error: ", e, file=sys.stderr)
        return "An error occurred", 500

@app.route('/delete_account', methods=['POST'])
def delete_account():
    username = session.get('username')
    if not username:
        return redirect(url_for('login'))

    try:
        cur = mysql.connection.cursor()
        # Fetch user_id
        cur.execute("SELECT user_id FROM Users WHERE user_name = %s", (username,))
        user_id = cur.fetchone()

        if user_id:
            # Delete reviews by user
            cur.execute("DELETE FROM Reviews WHERE user_id = %s", (user_id,))
            # Delete user account
            cur.execute("DELETE FROM Users WHERE user_id = %s", (user_id,))
            mysql.connection.commit()
        cur.close()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        mysql.connection.rollback()
        return "Failed to delete account", 500

    # Clear session and log out
    session.clear()
    return redirect(url_for('login'))


@app.route('/logout')
def logout():
    session.clear()  # Clears the entire session
    return redirect(url_for('login'))

@app.route('/compareproduct')
def compare_product():
    # Implement logic to retrieve products to compare from the database if needed
    return render_template('compare_product.html')

@app.route('/add_review', methods=['POST'])
def add_review():
    # Implement logic to add a product review
    return redirect(url_for('index'))

@app.route('/discounts_and_deals')
def discounts_and_deals():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT 
            p.product_id as 'Product ID', 
            p.product_name as 'Product Name', 
            CAST(p.actual_price AS SIGNED) as 'Price (₹)', 
            CAST(p.discounted_price AS SIGNED) as 'Discounted Price (₹)', 
            CONCAT(CAST(p.discount_percentage AS SIGNED), '%') as 'Total Discount (%)'
        FROM (
            SELECT 
                product_id, 
                product_name, 
                actual_price, 
                discounted_price, 
                discount_percentage,
                ROW_NUMBER() OVER (PARTITION BY product_name ORDER BY discount_percentage DESC) as rn
            FROM Products
            WHERE discounted_price IS NOT NULL AND actual_price > discounted_price
        ) p
        WHERE p.rn = 1
        ORDER BY p.discount_percentage DESC;
    """)
    discounts = cur.fetchall()
    cur.close()
    return discounts

@app.route('/under_fifty')
def under_fifty():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT 
            DISTINCT p.product_id, 
            p.product_name, 
            r.sentiment
        FROM 
            Products p
        JOIN 
            Reviews r ON p.product_id = r.product_id
        WHERE 
            p.discounted_price <= 50
        ORDER BY 
            p.discounted_price ASC;
    """)
    deal_fifty = cur.fetchall()
    cur.close()
    return deal_fifty

@app.route('/category_products/<category_name>')
def category_products(category_name):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT p.product_id, 
               p.product_name, 
               CAST(p.actual_price AS SIGNED) as Price, 
               p.rating,
               p.rating_count,
               (p.rating_count >= 5000) as is_best_seller
        FROM Products p
        JOIN CategoryAssignments ca ON p.product_id = ca.product_id
        JOIN Categories c ON ca.category_id = c.category_id
        WHERE c.category_name = %s
        ORDER BY p.rating DESC, p.rating_count DESC
        LIMIT 5;
    """, (category_name,))
    products = cur.fetchall()
    cur.close()
    return render_template('category_products.html', products=products, category_name=category_name)

@app.route('/get_product_details')
def get_product_details():
    product_name = request.args.get('product_name')
    cur = mysql.connection.cursor()
    
    # Adjust the SELECT statement to match your table schema and desired data
    query = """
SELECT 
    product_id,
    product_name,
    TRUNCATE(discounted_price, 0) AS discounted_price,
    TRUNCATE(discount_percentage, 0) AS discount_percentage,
    rating,
    about_product
FROM 
    Products 
WHERE 
    product_name = %s
LIMIT 1;
    """
    cur.execute(query, (product_name,))
    product = cur.fetchone()
    cur.close()
    
    if product:
        # Convert tuple to dict format
        product_data = {
            'product_id': product[0],
            'product_name': product[1],
            'discounted_price': product[2],
            'discount_percentage': product[3],
            'rating': product[4],
            'about_product': product[5]
        }
        return jsonify(product_data)
    else:
        return jsonify({'error': 'Product not found'}), 404
# Additional routes and logic as necessary

if __name__ == '__main__':
    app.run(debug=True)