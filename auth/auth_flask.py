from flask import Flask, render_template, request, redirect, url_for, session, send_file
import json_module_flask as db
import io
import pandas as pd
import webbrowser

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ================= LOGIN =================
@app.route("/", methods=["GET","POST"])
@app.route("/login", methods=["GET","POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = db.get_user(email)
        if user and db.verify_password(password, user["password_hash"]):
            session["logged_in"] = True
            session["user"] = user
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid email or password"
    return render_template("app.html", screen="login", title="Login", error=error, user=session.get("user"))

# ================= SIGNUP =================
@app.route("/signup", methods=["GET","POST"])
def signup():
    error = None
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        address = request.form.get("address")
        company = request.form.get("company")
        phone = request.form.get("phone")
        try:
            db.add_user(name,email,password,address,company,phone)
            return redirect(url_for("login"))
        except Exception as e:
            error = str(e)
    return render_template("app.html", screen="signup", title="Sign Up", error=error, user=session.get("user"))

# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ================= RESET PASSWORD REQUEST =================
@app.route("/reset_request", methods=["GET","POST"])
def reset_request():
    message = None
    if request.method == "POST":
        email = request.form.get("email")
        try:
            token = db.set_reset_token(email)
            db.send_reset_email(email, token)
            message = "Reset link sent! Check your email."
        except Exception as e:
            message = str(e)
    return render_template("app.html", screen="reset_request", title="Reset Password", message=message, user=session.get("user"))

# ================= RESET PASSWORD =================
@app.route("/reset_password/<token>", methods=["GET","POST"])
def reset_password(token):
    error = None
    user = db.get_user_by_token(token)
    if not user:
        return "Invalid or expired token", 400
    if request.method == "POST":
        new_pass = request.form.get("new_password")
        try:
            db.update_password(user["email"], new_pass)
            return redirect(url_for("login"))
        except Exception as e:
            error = str(e)
    return render_template("app.html", screen="reset_password", title="Set New Password", error=error, user=session.get("user"))

# ================= DASHBOARD =================
@app.route("/dashboard", methods=["GET","POST"])
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    user = session.get("user")
    status_message = ""
    results = []
    users_list = []

    if request.method == "POST" and not user.get("is_admin"):
        # Example process parameters
        p1 = request.form.get("p1")
        p2 = request.form.get("p2")
        status_message = f"Process ran with p1={p1}, p2={p2}"
        results = [{"Parameter1": p1, "Parameter2": p2, "Result":"Success"}]

    if user.get("is_admin"):
        users_list = db.get_all_users()

    return render_template(
        "app.html",
        screen="dashboard",
        title="Dashboard",
        status_message=status_message,
        results=results,
        users_list=users_list,
        user=user
    )

# ================= DOWNLOAD EXCEL =================
@app.route("/download_excel")
def download_excel():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    # Example data; replace with actual process results
    data = [{"Parameter1":"A","Parameter2":"B","Result":"Success"}]
    df = pd.DataFrame(data)
    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return send_file(
        output,
        download_name="results.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ================= ADMIN EDIT USER =================
@app.route("/edit_user/<int:user_id>", methods=["POST"])
def edit_user(user_id):
    if not session.get("logged_in") or not session["user"].get("is_admin"):
        return redirect(url_for("login"))
    name = request.form.get("name")
    email = request.form.get("email")
    address = request.form.get("address")
    company = request.form.get("company")
    phone = request.form.get("phone")
    is_admin = True if request.form.get("is_admin")=="on" else False
    try:
        db.update_user(user_id, name, email, address, company, phone, is_admin)
        if session["user"]["id"] == user_id:
            session["user"] = db.get_user(email)
    except Exception as e:
        print("Edit user error:", e)
    return redirect(url_for("dashboard"))

# ================= ADMIN DELETE USER =================
@app.route("/delete_user/<int:user_id>")
def delete_user(user_id):
    if not session.get("logged_in") or not session["user"].get("is_admin"):
        return redirect(url_for("login"))
    try:
        db.delete_user(user_id)
    except Exception as e:
        print("Delete user error:", e)
    return redirect(url_for("dashboard"))

# ================= RUN APP =================
if __name__=="__main__":
    webbrowser.open("http://127.0.0.1:5000")
    app.run(debug=True)
