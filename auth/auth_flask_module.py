# auth/auth_flask_module.py
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
import bcrypt
from datetime import datetime, timedelta
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
auth_dir = os.path.join(current_dir, "Auth")
if auth_dir not in sys.path:
    sys.path.append(auth_dir)

from .json_module_flask import (
    get_user, get_user_count, add_user, update_password,
    set_reset_token, get_user_by_token, update_user, delete_user,
    send_reset_email, get_all_users
)

app = Flask(__name__)
app.secret_key = "supersecretkey"  # change this in production

# ===== HELPER: COOKIE MANAGEMENT =====
def set_cookie(resp, key, value, days_expire=30):
    expire_date = datetime.now() + timedelta(days=days_expire)
    resp.set_cookie(key, value, expires=expire_date)

def delete_cookie(resp, key):
    resp.set_cookie(key, "", expires=0)

# ===== LOGIN =====
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        remember = request.form.get("remember")
        user = get_user(email)
        if user and bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
            session['logged_in'] = True
            session['user'] = user
            resp = make_response(redirect(url_for("dashboard")))
            if remember:
                set_cookie(resp, "auth_email", email)
                set_cookie(resp, "auth_password", password)
            else:
                delete_cookie(resp, "auth_email")
                delete_cookie(resp, "auth_password")
            return resp
        else:
            flash("Invalid email or password", "danger")
    return render_template("login.html")

# ===== SIGNUP =====
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        address = request.form.get("address")
        company = request.form.get("company")
        phone = request.form.get("phone")
        if get_user(email):
            flash("Email already registered", "danger")
        else:
            add_user(name, email, password, address, company, phone)
            if get_user_count() == 1:
                flash("Account created! You are the admin. Please log in.", "success")
            else:
                flash("Account created! Please log in.", "success")
            return redirect(url_for("login"))
    return render_template("signup.html")

# ===== RESET PASSWORD =====
@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = get_user_by_token(token)
    if not user:
        flash("Invalid or expired reset link.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        new_pass = request.form.get("new_password")
        update_password(user["email"], new_pass)
        flash("Password updated! You can now log in.", "success")
        return redirect(url_for("login"))
    return render_template("reset_password.html", token=token)

# ===== DASHBOARD / ADMIN PANEL =====
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if not session.get("logged_in"):
        # Check cookies for auto-login
        email = request.cookies.get("auth_email")
        password = request.cookies.get("auth_password")
        if email and password:
            user = get_user(email)
            if user and bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
                session['logged_in'] = True
                session['user'] = user
        else:
            return redirect(url_for("login"))

    user = session.get("user")
    if not user:
        return redirect(url_for("login"))

    if user.get("is_admin"):
        search_query = request.args.get("search", "")
        users = get_all_users(search_query)
        if request.method == "POST":
            for u in users:
                uid = str(u["id"])
                if f"save_{uid}" in request.form:
                    update_user(
                        u['id'],
                        request.form.get(f"name_{uid}"),
                        request.form.get(f"email_{uid}"),
                        request.form.get(f"address_{uid}"),
                        request.form.get(f"company_{uid}"),
                        request.form.get(f"phone_{uid}"),
                        request.form.get(f"admin_{uid}") == "on"
                    )
                    flash("User updated", "success")
                    return redirect(url_for("dashboard"))
                if f"delete_{uid}" in request.form:
                    delete_user(u['id'])
                    flash("User deleted", "warning")
                    return redirect(url_for("dashboard"))
        return render_template("admin_dashboard.html", users=users)
    else:
        flash("You are logged in as a regular user.", "info")
        return render_template("user_dashboard.html")

# ===== LOGOUT =====
@app.route("/logout")
def logout():
    session.clear()
    resp = make_response(redirect(url_for("login")))
    delete_cookie(resp, "auth_email")
    delete_cookie(resp, "auth_password")
    return resp

if __name__ == "__main__":
    app.run(debug=True)
