import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
import datetime
import time

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    bought = db.execute("SELECT symbol, shares FROM home WHERE id = :id", id=session["user_id"])

    for row in bought:
        symbol = row["symbol"]
        sym = lookup(symbol)
        price = sym["price"]
        change = sym["change"]

        db.execute("UPDATE home SET price = :price, change = :change WHERE id = :id and symbol = :symbol", price=usd(price), change=change, id=session["user_id"], symbol=symbol)

    userName = db.execute("SELECT username FROM users WHERE id = :id", id=session["user_id"])

    topStock = db.execute("SELECT * FROM home WHERE id = :id ORDER BY random() LIMIT 3", id=session["user_id"])

    username = userName[0]["username"]

    return render_template("home.html", home = topStock, username = username)



@app.route("/owned")
@login_required
def owned():
    """Show portfolio of stocks"""

    bought = db.execute("SELECT symbol, shares FROM home WHERE id = :id", id=session["user_id"])

    currentCash = db.execute("SELECT cash, username FROM users WHERE id = :id", id=session["user_id"])

    grandTotal = currentCash[0]["cash"]

    for row in bought:
        symbol = row["symbol"]
        sym = lookup(symbol)
        price = sym["price"]
        shares = row["shares"]
        change = sym["change"]
        total = shares * price

        grandTotal += total

        db.execute("UPDATE home SET price = :price, change = :change, total = :total WHERE id = :id and symbol = :symbol", price=usd(price), change=change, total=usd(total), id=session["user_id"], symbol=symbol)

    updatedHome = db.execute("SELECT * FROM home WHERE id = :id", id=session["user_id"])

    username = currentCash[0]["username"]

    return render_template("owned.html", owned = updatedHome, cash = usd(currentCash[0]["cash"]), total = usd(grandTotal), username = username)



@app.route("/buymore", methods=["POST"])
@login_required
def buymore():
    """Buy shares of stock from owned"""

    if not request.form.get("symbol"):
        flash("Error 400 : Must enter a Stock Symbol", 'danger')
        return redirect("/owned")

    elif not request.form.get("shares"):
        flash("Error 403 : Shares field can't be left empty.", 'danger')
        return redirect("/owned")

    sym = lookup(request.form.get("symbol"))

    if not sym:
        flash("Error 404 : Symbol entered does not exist.", 'warning')
        return redirect("/owned")

    current = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])

    shares = int(request.form.get("shares"))

    price = sym["price"]

    symbolInput = '\"%s\"' % sym["symbol"]

    asked = float(shares * price)

    now = datetime.datetime.now()

    mytime = now.strftime("%Y%m%d%H%M%S")
    times = now.strftime("%d %B, %Y  %I:%M:%S %p")

    if not current or asked > float(current[0]["cash"]):
        flash("Not enough cash. Add to Wallet.", 'warning')
        return redirect("/owned")
    else:
        db.execute("INSERT INTO history (mytime, symbol, shares, price, times, id) VALUES (:mytime, :symbol, :shares, :price, :times, :id)", mytime=int(mytime), symbol=sym["symbol"], shares=shares, price=usd(sym["price"]), times=times, id=session["user_id"])

        db.execute("UPDATE users SET cash = cash - :asked WHERE id = :id", asked=asked, id=session["user_id"])


        if not db.execute("SELECT shares FROM home WHERE id = :id and symbol = :symbol", id=session["user_id"], symbol=sym["symbol"]):
            db.execute("INSERT INTO home (id, symbol, name, shares, price, total, change) VALUES (:id, :symbol, :name, :shares, :price, :total, :change)", id=session["user_id"], symbol=sym["symbol"], name=sym["name"], shares=shares, price=usd(sym["price"]), total=usd(asked), change=sym["change"])
        else:
            db.execute("UPDATE home SET shares = shares + :bought WHERE id = :id AND symbol = :symbol", bought=shares, id=session["user_id"], symbol=sym["symbol"])


        flash("Shares Bought!!", 'success')
        return redirect("/owned")


@app.route("/sellsome", methods=["POST"])
@login_required
def sellsome():
    """Sell shares of stock from owned"""

    if not request.form.get("symbol"):
        flash("Error 400 : Must select a Stock Symbol", 'danger')
        return redirect("/owned")

    elif not request.form.get("shares"):
        flash("Error 403 : Shares field can't be left empty.", 'danger')
        return redirect("/owned")

    sharestoSell = int(request.form.get("shares"))

    sym = lookup(request.form.get("symbol"))

    currentShares = db.execute("SELECT shares FROM home WHERE id = :id AND symbol = :symbol", id=session["user_id"], symbol=sym["symbol"])

    price = sym["price"]

    asked = float(sharestoSell * price)

    showshares = -sharestoSell

    now = datetime.datetime.now()

    mytime = now.strftime("%Y%m%d%H%M%S")
    times = now.strftime("%d %B, %Y  %I:%M:%S %p")

    if sharestoSell > currentShares[0]["shares"]:
        flash("You can not sell more shares than you have.", 'warning')
        return redirect("/owned")

    elif sharestoSell == currentShares[0]["shares"]:
        db.execute("INSERT INTO history (mytime, symbol, shares, price, times, id) VALUES (:mytime, :symbol, :shares, :price, :times, :id)", mytime=int(mytime), symbol=sym["symbol"], shares=showshares, price=usd(sym["price"]), times=times, id=session["user_id"])

        db.execute("UPDATE users SET cash = cash + :asked WHERE id = :id", asked=asked, id=session["user_id"])

        db.execute("DELETE FROM home WHERE id = :id AND symbol = :symbol", id=session["user_id"], symbol=sym["symbol"])

        flash("Sold!!", 'success')
        return redirect("/owned")

    else:
        db.execute("INSERT INTO history (mytime, symbol, shares, price, times, id) VALUES (:mytime, :symbol, :shares, :price, :times, :id)", mytime=int(mytime), symbol=sym["symbol"], shares=showshares, price=usd(sym["price"]), times=times, id=session["user_id"])

        db.execute("UPDATE users SET cash = cash + :asked WHERE id = :id", asked=asked, id=session["user_id"])

        db.execute("UPDATE home SET shares = shares - :bought WHERE id = :id AND symbol = :symbol", bought=sharestoSell, id=session["user_id"], symbol=sym["symbol"])

        flash("Sold!!", 'success')
        return redirect("/owned")




@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        if not request.form.get("symbol"):
            flash("Error 400 : Must enter a Stock Symbol", 'danger')
            return redirect("/buy")

        elif not request.form.get("shares"):
            flash("Error 403 : Shares field can't be left empty.", 'danger')
            return redirect("/buy")

        sym = lookup(request.form.get("symbol"))

        if not sym:
            flash("Error 404 : Symbol entered does not exist.", 'warning')
            return redirect("/buy")

        current = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])

        shares = int(request.form.get("shares"))

        price = sym["price"]

        symbolInput = '\"%s\"' % sym["symbol"]

        asked = float(shares * price)

        now = datetime.datetime.now()

        mytime = now.strftime("%Y%m%d%H%M%S")
        times = now.strftime("%d %B, %Y  %I:%M:%S %p")

        if not current or asked > float(current[0]["cash"]):
            flash("Not enough cash. Add to Wallet.", 'warning')
            return redirect("/buy")
        else:
            db.execute("INSERT INTO history (mytime, symbol, shares, price, times, id) VALUES (:mytime, :symbol, :shares, :price, :times, :id)", mytime=int(mytime), symbol=sym["symbol"], shares=shares, price=usd(sym["price"]), times=times, id=session["user_id"])

            db.execute("UPDATE users SET cash = cash - :asked WHERE id = :id", asked=asked, id=session["user_id"])


            if not db.execute("SELECT shares FROM home WHERE id = :id and symbol = :symbol", id=session["user_id"], symbol=sym["symbol"]):
                db.execute("INSERT INTO home (id, symbol, name, shares, price, total, change) VALUES (:id, :symbol, :name, :shares, :price, :total, :change)", id=session["user_id"], symbol=sym["symbol"], name=sym["name"], shares=shares, price=usd(sym["price"]), total=usd(asked), change=sym["change"])
            else:
                db.execute("UPDATE home SET shares = shares + :bought WHERE id = :id AND symbol = :symbol", bought=shares, id=session["user_id"], symbol=sym["symbol"])


            flash("Shares Bought!!", 'success')
            return redirect("/owned")

    else:

        username = db.execute("SELECT username FROM users WHERE id = :id", id=session["user_id"])

        return render_template("buy.html", username=username[0]["username"])



@app.route("/about")
@login_required
def about():
    return render_template("about.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    history = db.execute("SELECT * FROM history WHERE id = :id ORDER BY mytime DESC", id=session["user_id"])
    username = db.execute("SELECT username FROM users WHERE id = :id", id=session["user_id"])

    return render_template("history.html", history=history, username=username[0]["username"])


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":
        return render_template("login.html")

    # Forget any user_id  # moved in if POST as it was creating problem for showing alert
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            flash("Error 403 : Must provide Username", 'danger')
            return redirect("/login")

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Error 403 : Must provide Password", 'danger')
            return redirect("/login")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            flash("Error: Invalid Username/Password", 'danger')
            return redirect("/login")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        flash("Welcome!!", 'primary')

        # Redirect user to home page
        return redirect("/")




@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":

        user = db.execute("SELECT cash, username FROM users WHERE id = :id", id=session["user_id"])

        symbols = lookup(request.form.get("symbol"))

        if not request.form.get("symbol"):
            flash("Error 400 : Must provide Stock's Symbol", 'danger')
            return redirect("/quote")

        if not symbols:
            flash("Error 404 : Stock's Symbol not found.", 'warning')
            return redirect("/quote")

        return render_template("quote.html", symbols=symbols, username=user[0]["username"])

    else:

        user = db.execute("SELECT cash, username FROM users WHERE id = :id", id=session["user_id"])

        return render_template("quote.html", username=user[0]["username"])


@app.route("/profile")
@login_required
def profile():
    user = db.execute("SELECT cash, username FROM users WHERE id = :id", id=session["user_id"])

    return render_template("profile.html", username=user[0]["username"])



@app.route("/username", methods=["POST"])
@login_required
def username():
    """Change Username"""

    if not request.form.get("newuser"):
        flash("Error 403 : Must provide Username", 'danger')
        return redirect("/profile")

    elif len(request.form.get("newuser")) > 10:
        flash("Username is too long. Should not be more than 10 letters.", 'warning')
        return redirect("/profile")

    elif len(request.form.get("newuser")) < 4:
        flash("Username is too short. Should not be less than 4 letters.", 'warning')
        return redirect("/profile")

    username=request.form.get("newuser")

    registered = db.execute("SELECT username FROM users")
    registeration = db.execute("SELECT COUNT(username) FROM users")

    for i in range(registeration[0]["COUNT(username)"]):
        if username == registered[i]["username"]:
            flash("Username already taken.", 'danger')
            return redirect("/profile")

    for i in range(len(username)):
        if username[i] == " ":
            flash("Username cannot contain a Space", 'warning')
            return redirect("/profile")
        elif not username[i].isalnum():
            flash("Username should contain only letters and digits.", 'warning')
            return redirect("/profile")

    if not request.form.get("userpass"):
        flash("Error 403 : Must provide Password", 'danger')
        return redirect("/profile")

    userpass=request.form.get("userpass")

    password=db.execute("SELECT hash FROM users WHERE id =:id", id=session["user_id"])

    if len(password) != 1 or not check_password_hash(password[0]["hash"], userpass):
        flash("Error: Invalid Password", 'danger')
        return redirect("/profile")
    else:
        db.execute("UPDATE users SET username = :username WHERE id = :id", username=username, id=session["user_id"])

    flash("Username changed Successfully!!", 'primary')
    return redirect("/profile")



@app.route("/password", methods=["POST"])
@login_required
def password():
    """Change Password"""

    if not request.form.get("oldpass"):
        flash("Error 403 : Must provide Old Password", 'danger')
        return redirect("/profile")

    oldpass=request.form.get("oldpass")

    password=db.execute("SELECT hash FROM users WHERE id =:id", id=session["user_id"])

    if len(password) != 1 or not check_password_hash(password[0]["hash"], oldpass):
        flash("Error: Old Password Invalid", 'danger')
        return redirect("/profile")
    else:
        if not request.form.get("newpass"):
            flash("Error 403 : Must provide New Password", 'danger')
            return redirect("/profile")

        elif len(request.form.get("newpass")) < 8:
            flash("Password is too short. Enter atleast 8 characters.", 'warning')
            return redirect("/profile")

        newpass=request.form.get("newpass")
        digit=0

        for i in range(len(newpass)):
            if newpass[i] == " ":
                flash("Password cannot contain a 'Space'", 'warning')
                return redirect("/profile")
            elif not newpass[i].isalnum():
                flash("Password should contain only letters and digits.", 'warning')
                return redirect("/profile")
            elif newpass[i].isdigit():
                digit += 1

        if digit == 0:
            flash("Password should contain atleast one number.", 'warning')
            return redirect("/profile")

        if not request.form.get("newcon"):
            flash("Must provide Password Again for confirmation", 'danger')
            return redirect("/profile")

        newcon=request.form.get("newcon")

        if newcon != newpass:
            flash("Error: Password did not match", 'danger')
            return redirect("/profile")
        else:
            db.execute("UPDATE users SET hash = :hash WHERE id = :id", hash=generate_password_hash(newpass), id=session["user_id"])

        flash("Password changed Successfully!!", 'primary')
        return redirect("/profile")



@app.route("/delete", methods=["POST"])
@login_required
def delete():
    """Delete Account"""

    if not request.form.get("delpass"):
        flash("Error 403 : Must provide Password", 'danger')
        return redirect("/profile")

    delpass=request.form.get("delpass")

    password=db.execute("SELECT hash FROM users WHERE id =:id", id=session["user_id"])

    if len(password) != 1 or not check_password_hash(password[0]["hash"], delpass):
        flash("Error: Invalid Password", 'danger')
        return redirect("/profile")
    else:
        db.execute("DELETE FROM users WHERE id = :id", id=session["user_id"])
        db.execute("DELETE FROM home WHERE id = :id", id=session["user_id"])
        db.execute("DELETE FROM history WHERE id = :id", id=session["user_id"])

        flash("Account Deleted!!", 'primary')
        return redirect("/login")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        if not request.form.get("username"):
            flash("Error 403 : Must provide Username", 'danger')
            return redirect("/register")

        elif len(request.form.get("username")) > 10:
            flash("Username is too long. Should not be more than 10 letters.", 'warning')
            return redirect("/register")

        elif len(request.form.get("username")) < 4:
            flash("Username is too short. Should not be less than 4 letters.", 'warning')
            return redirect("/register")

        username=request.form.get("username")

        registered = db.execute("SELECT username FROM users")
        i=0

        while registered[i]["username"]:
            if username == registered[i]["username"]:
                flash("Username already taken.", 'danger')
                return redirect("/register")
            if not registered[i]["username"]:
                break
            i += 1;

        for i in range(len(username)):
            if username[i] == " ":
                flash("Username cannot contain a Space", 'warning')
                return redirect("/register")
            elif not username[i].isalnum():
                flash("Username should contain only letters and digits.", 'warning')
                return redirect("/register")

        if not request.form.get("password"):
            flash("Error 403 : Must provide Password", 'danger')
            return redirect("/register")

        elif len(request.form.get("password")) < 8:
            flash("Password is too short. Enter atleast 8 characters, for it to be stronger.", 'warning')
            return redirect("/register")

        password=request.form.get("password")
        digit=0

        for i in range(len(password)):
            if password[i] == " ":
                flash("Password cannot contain a 'Space'", 'warning')
                return redirect("/register")
            elif not password[i].isalnum():
                flash("Password should contain only letters and digits.", 'warning')
                return redirect("/register")
            elif password[i].isdigit():
                digit += 1

        if digit == 0:
            flash("Password should contain atleast one number.", 'warning')
            return redirect("/register")

        if not request.form.get("confirmation"):
            flash("Error 403 : Must provide Password Again for confirmation", 'danger')
            return redirect("/register")

        confirmation=request.form.get("confirmation")

        if confirmation != password:
            flash("Error: Password did not match", 'danger')
            return redirect("/register")

        rows = db.execute("INSERT INTO users(username,hash) VALUES (:username,:hash)", username=request.form.get("username"), hash=generate_password_hash(password))

        flash("Registeration successfull. Login to Start.", 'success')
        return redirect("/login")


    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":

        if not request.form.get("symbol"):
            flash("Error 400 : Must select a Stock Symbol", 'danger')
            return redirect("/sell")

        elif not request.form.get("shares"):
            flash("Error 403 : Shares field can't be left empty.", 'danger')
            return redirect("/sell")

        sharestoSell = int(request.form.get("shares"))

        sym = lookup(request.form.get("symbol"))

        currentShares = db.execute("SELECT shares FROM home WHERE id = :id AND symbol = :symbol", id=session["user_id"], symbol=sym["symbol"])

        price = sym["price"]

        asked = float(sharestoSell * price)

        showshares = -sharestoSell

        now = datetime.datetime.now()

        mytime = now.strftime("%Y%m%d%H%M%S")
        times = now.strftime("%d %B, %Y  %I:%M:%S %p")

        if sharestoSell > currentShares[0]["shares"]:
            flash("You can not sell more shares than you have.", 'warning')
            return redirect("/sell")

        elif sharestoSell == currentShares[0]["shares"]:
            db.execute("INSERT INTO history (mytime, symbol, shares, price, times, id) VALUES (:mytime, :symbol, :shares, :price, :times, :id)", mytime=int(mytime), symbol=sym["symbol"], shares=showshares, price=usd(sym["price"]), times=times, id=session["user_id"])

            db.execute("UPDATE users SET cash = cash + :asked WHERE id = :id", asked=asked, id=session["user_id"])

            db.execute("DELETE FROM home WHERE id = :id AND symbol = :symbol", id=session["user_id"], symbol=sym["symbol"])

            flash("Sold!!", 'success')
            return redirect("/owned")

        elif sharestoSell < currentShares[0]["shares"]:

            db.execute("INSERT INTO history (mytime, symbol, shares, price, times, id) VALUES (:mytime, :symbol, :shares, :price, :times, :id)", mytime=int(mytime), symbol=sym["symbol"], shares=showshares, price=usd(sym["price"]), times=times, id=session["user_id"])

            db.execute("UPDATE users SET cash = cash + :asked WHERE id = :id", asked=asked, id=session["user_id"])

            db.execute("UPDATE home SET shares = shares - :bought WHERE id = :id AND symbol = :symbol", bought=sharestoSell, id=session["user_id"], symbol=sym["symbol"])

            flash("Sold!!", 'success')
            return redirect("/owned")

    else:

        username = db.execute("SELECT username FROM users WHERE id = :id", id=session["user_id"])

        symbols = db.execute("SELECT symbol FROM home WHERE id = :id", id=session["user_id"])

        return render_template("sell.html", symbols=symbols, username=username[0]["username"])



@app.route("/wallet", methods=["GET", "POST"])
@login_required
def wallet():
    """Add to wallet"""

    if request.method == "POST":

        if not request.form.get("amount"):
            flash("Must enter an amount to take loan.", 'danger')
            return redirect("/wallet")

        loan = float(request.form.get("amount"))

        now = datetime.datetime.now()

        mytime = now.strftime("%Y%m%d%H%M%S")
        times = now.strftime("%d %B, %Y  %I:%M:%S %p")

        db.execute("INSERT INTO history (mytime, symbol, shares, price, times, id) VALUES (:mytime, 'LOAN', -999999999, :amount, :times, :id)", mytime=int(mytime), amount=usd(loan), times=times, id=session["user_id"])

        db.execute("UPDATE users SET cash = cash + :loan WHERE id = :id", loan=loan, id=session["user_id"])

        flash("Amount added Successfully!!", 'success')
        return redirect("/wallet")

    else:

        user = db.execute("SELECT cash, username FROM users WHERE id = :id", id=session["user_id"])
        cash = user[0]["cash"]

        bought = db.execute("SELECT symbol, shares FROM home WHERE id = :id", id=session["user_id"])

        additional = 0

        for row in bought:
            symbol = row["symbol"]
            sym = lookup(symbol)
            price = sym["price"]
            shares = row["shares"]
            total = shares * price

            additional += total

        return render_template("wallet.html", cash=usd(cash), additional=usd(additional), username=user[0]["username"])


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
