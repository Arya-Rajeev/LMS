import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "csi_dhanuvachapuram_secure_production_key_2026_matrix"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "library_catalog.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_production_system():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            category TEXT NOT NULL,
            image_url TEXT,
            total_copies INTEGER NOT NULL,
            available_copies INTEGER NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS members (
            member_id TEXT PRIMARY KEY,
            member_name TEXT NOT NULL,
            member_phone TEXT NOT NULL,
            registration_date TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER,
            member_id TEXT NOT NULL,
            user_name TEXT NOT NULL,
            borrower_phone TEXT NOT NULL,
            issue_date TEXT NOT NULL,
            return_date TEXT NOT NULL,
            status TEXT DEFAULT 'Active',
            FOREIGN KEY (book_id) REFERENCES books (id),
            FOREIGN KEY (member_id) REFERENCES members (member_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_key TEXT UNIQUE,
            config_value TEXT NOT NULL
        )
    ''')
    
    try:
        cursor.execute("INSERT OR IGNORE INTO system_config (config_key, config_value) VALUES ('admin_password', 'csidnv2026')")
    except sqlite3.Error:
        pass

    cursor.execute("SELECT COUNT(*) FROM books")
    if cursor.fetchone()[0] == 0:
        initial_stock = [
            ("Aarachar (ആരാച്ചാർ)", "K.R. Meera", "Novel", "https://images.unsplash.com/photo-1544947950-fa07a98d237f?q=80&w=400", 5, 5),
            ("Randamoozham (രണ്ടാമൂഴം)", "M.T. Vasudevan Nair", "Fiction", "https://images.unsplash.com/photo-1512820790803-83ca734da794?q=80&w=400", 3, 3),
            ("Pathummayude Aadu (പാത്തുമ്മയുടെ ആട്)", "Vaikom Muhammad Basheer", "Classic", "https://images.unsplash.com/photo-1543002588-bfa74002ed7e?q=80&w=400", 4, 4)
        ]
        cursor.executemany("INSERT INTO books (title, author, category, image_url, total_copies, available_copies) VALUES (?, ?, ?, ?, ?, ?)", initial_stock)
        
    conn.commit()
    conn.close()


@app.route("/")
def home():
    search_query = request.args.get("search", "").strip()
    category_filter = request.args.get("category", "All")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT category FROM books ORDER BY category ASC")
    categories = [row["category"] for row in cursor.fetchall()]

    query = "SELECT * FROM books WHERE 1=1"
    params = []

    if search_query:
        query += " AND (title LIKE ? OR author LIKE ? OR category LIKE ?)"
        params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])

    if category_filter != "All":
        query += " AND category = ?"
        params.append(category_filter)

    query += " ORDER BY title ASC"
    cursor.execute(query, params)
    books = cursor.fetchall()
    conn.close()

    return render_template("home.html", books=books, categories=categories, selected_category=category_filter, search_query=search_query)


@app.route("/book/<int:book_id>")
def book_detail(book_id):
    conn = get_db_connection()
    book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    conn.close()
    if not book:
        return "Book Asset Registry Error", 404
    return render_template("book_detail.html", book=book)


@app.route("/book/<int:book_id>/borrow", methods=["POST"])
def borrow_book(book_id):
    member_id = request.form.get("member_id", "").strip().upper()
    user_name = request.form.get("user_name", "").strip()
    borrower_phone = request.form.get("borrower_phone", "").strip()

    if not member_id or not user_name or not borrower_phone:
        flash("Please fill out all borrower fields completely.", "error")
        return redirect(url_for("book_detail", book_id=book_id))

    conn = get_db_connection()
    
    member = conn.execute("SELECT * FROM members WHERE member_id = ?", (member_id,)).fetchone()
    if not member:
        conn.close()
        flash("Access Denied! Invalid or Unregistered Membership ID. Please register offline first.", "error")
        return redirect(url_for("book_detail", book_id=book_id))

    book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()

    if book and book["available_copies"] > 0:
        issue_date = datetime.now().strftime("%Y-%m-%d")
        return_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

        conn.execute("UPDATE books SET available_copies = available_copies - 1 WHERE id = ?", (book_id,))
        conn.execute("INSERT INTO issues (book_id, member_id, user_name, borrower_phone, issue_date, return_date, status) VALUES (?, ?, ?, ?, ?, ?, 'Active')", 
                     (book_id, member_id, user_name, borrower_phone, issue_date, return_date))
        conn.commit()
        flash(f'Success! Book allocated. Automatically due back in 30 days.', "success")
    else:
        flash("Allocation failed. Selected text volume is out of stock.", "error")

    conn.close()
    return redirect(url_for("home"))


@app.route("/secretadmin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password")
        
        conn = get_db_connection()
        db_pass = conn.execute("SELECT config_value FROM system_config WHERE config_key = 'admin_password'").fetchone()
        conn.close()

        if db_pass and password == db_pass["config_value"]:
            session["is_admin"] = True
            flash("Welcome back, Access granted to CSI Admin Portal.", "success")
            return redirect(url_for("admin_portal"))
        else:
            flash("Access Violation! Invalid security credential password.", "error")

    return render_template("admin_login.html")


@app.route("/admin", methods=["GET", "POST"])
def admin_portal():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    conn = get_db_connection()

    if request.method == "POST":
        form_type = request.form.get("form_type")
        
        if form_type == "add_book":
            title = request.form["title"].strip()
            author = request.form["author"].strip()
            copies = int(request.form["copies"])
            
            selected_cat = request.form.get("category_select")
            new_cat = request.form.get("category_new", "").strip()

            if selected_cat == "NEW_CATEGORY" and new_cat:
                category = new_cat
            elif selected_cat and selected_cat != "NEW_CATEGORY":
                category = selected_cat
            else:
                category = "General"

            final_image_path = "https://images.unsplash.com/photo-1543002588-bfa74002ed7e?q=80&w=400"
            
            if 'book_image' in request.files:
                file = request.files['book_image']
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    unique_filename = f"{int(datetime.now().timestamp())}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                    final_image_path = f"/static/uploads/{unique_filename}"

            conn.execute("INSERT INTO books (title, author, category, image_url, total_copies, available_copies) VALUES (?, ?, ?, ?, ?, ?)",
                         (title, author, category, final_image_path, copies, copies))
            conn.commit()
            flash(f'"{title}" cataloged successfully.', "success")
            
        elif form_type == "add_member":
            m_id = request.form["member_id"].strip().upper()
            m_name = request.form["member_name"].strip()
            m_phone = request.form["member_phone"].strip()
            reg_date = datetime.now().strftime("%Y-%m-%d")

            try:
                conn.execute("INSERT INTO members (member_id, member_name, member_phone, registration_date) VALUES (?, ?, ?, ?)",
                             (m_id, m_name, m_phone, reg_date))
                conn.commit()
                flash(f"Member ID '{m_id}' activated successfully.", "success")
            except sqlite3.IntegrityError:
                flash("Database Clash! Member ID already exists.", "error")
                
        return redirect(url_for("admin_portal"))

    books_by_cat = conn.execute("SELECT * FROM books ORDER BY category ASC, title ASC").fetchall()
    registered_members = conn.execute("SELECT * FROM members ORDER BY member_id ASC").fetchall()
    active_logs = conn.execute("""
        SELECT issues.*, books.title FROM issues 
        JOIN books ON issues.book_id = books.id
        WHERE issues.status = 'Active' ORDER BY issues.id DESC
    """).fetchall()
    
    conn.close()
    return render_template("admin.html", books=books_by_cat, logs=active_logs, members=registered_members)


@app.route("/admin/change-password", methods=["POST"])
def change_password():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    new_password = request.form.get("new_password", "").strip()
    if len(new_password) < 4:
        flash("Password validation error. Minimally 4 characters required.", "error")
        return redirect(url_for("admin_portal"))

    conn = get_db_connection()
    conn.execute("UPDATE system_config SET config_value = ? WHERE config_key = 'admin_password'", (new_password,))
    conn.commit()
    conn.close()

    flash("Master access password customized successfully.", "success")
    return redirect(url_for("admin_portal"))


@app.route("/admin/return/<int:issue_id>", methods=["POST"])
def return_book_action(issue_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    issue = conn.execute("SELECT * FROM issues WHERE id = ?", (issue_id,)).fetchone()
    
    if issue:
        conn.execute("UPDATE books SET available_copies = available_copies + 1 WHERE id = ?", (issue["book_id"],))
        conn.execute("UPDATE issues SET status = 'Returned' WHERE id = ?", (issue_id,))
        conn.commit()
        flash("Book checked back in successfully.", "success")
    
    conn.close()
    return redirect(url_for("admin_portal"))


@app.route("/admin/edit/<int:book_id>", methods=["GET", "POST"])
def edit_book(book_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()

    if request.method == "POST":
        title = request.form["title"].strip()
        author = request.form["author"].strip()
        category = request.form["category"].strip()
        total_copies = int(request.form["copies"])
        
        diff = total_copies - book["total_copies"]
        new_avail = book["available_copies"] + diff

        conn.execute("""
            UPDATE books SET title = ?, author = ?, category = ?, total_copies = ?, available_copies = ? 
            WHERE id = ?
        """, (title, author, category, total_copies, new_avail, book_id))
        conn.commit()
        conn.close()
        flash(f'"{title}" inventory records updated.', "success")
        return redirect(url_for("admin_portal"))

    conn.close()
    return render_template("edit_book.html", book=book)


@app.route("/admin/edit-member/<string:member_id>", methods=["GET", "POST"])
def edit_member(member_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    member = conn.execute("SELECT * FROM members WHERE member_id = ?", (member_id,)).fetchone()

    if request.method == "POST":
        name = request.form["member_name"].strip()
        phone = request.form["member_phone"].strip()

        conn.execute("""
            UPDATE members SET member_name = ?, member_phone = ? WHERE member_id = ?
        """, (name, phone, member_id))
        conn.commit()
        conn.close()
        flash(f"Profile for Member ID '{member_id}' updated successfully.", "success")
        return redirect(url_for("admin_portal"))

    conn.close()
    if not member:
        return "Member File Reference Error", 404
    return render_template("edit_member.html", member=member)


@app.route("/admin/delete/<int:book_id>", methods=["POST"])
def delete_book_action(book_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
    conn.execute("DELETE FROM issues WHERE book_id = ?", (book_id,))
    conn.commit()
    conn.close()
    
    flash("Item permanently deleted.", "success")
    return redirect(url_for("admin_portal"))


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("home"))


if __name__ == "__main__":
    init_production_system()
    app.run(debug=True)