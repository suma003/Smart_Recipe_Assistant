import os
from uuid import uuid4
from flask import Flask, render_template, request, redirect, url_for, session, flash
from database import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "smart-recipe-assistant-dev-key")

# =========================================================
# FILE UPLOAD CONFIGURATION
# =========================================================
UPLOAD_FOLDER = os.path.join("static", "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def allowed_image(filename):
    return (
        bool(filename)
        and "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS
    )


def save_uploaded_image(image_file):
    if not image_file or not image_file.filename:
        return None

    if not allowed_image(image_file.filename):
        raise ValueError("Only PNG, JPG, JPEG, GIF, and WEBP images are allowed.")

    original_name = secure_filename(image_file.filename)
    extension = original_name.rsplit(".", 1)[1].lower()
    unique_name = f"{uuid4().hex}.{extension}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
    image_file.save(filepath)

    return url_for("static", filename=f"uploads/{unique_name}")


# =========================================================
# HOME
# =========================================================
@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


# =========================================================
# REGISTER
# =========================================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if not name or not email or not password:
            flash("All fields are required.")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("Password must be at least 6 characters.")
            return redirect(url_for("register"))

        connection = get_db_connection()
        existing_user = connection.execute(
            "SELECT UserID FROM Users WHERE Email = ?", (email,)
        ).fetchone()

        if existing_user:
            connection.close()
            flash("Email already exists.")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)
        connection.execute(
            "INSERT INTO Users (Name, Email, Password) VALUES (?, ?, ?)",
            (name, email, password_hash)
        )
        connection.commit()
        connection.close()

        flash("Registration successful! Please login.")
        return redirect(url_for("login"))

    return render_template("register.html")


# =========================================================
# LOGIN
# =========================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        if session.get("user_role") == "Admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        connection = get_db_connection()
        user = connection.execute(
            "SELECT * FROM Users WHERE Email = ?", (email,)
        ).fetchone()
        connection.close()

        if user and check_password_hash(user["Password"], password):
            session["user_id"] = user["UserID"]
            session["user_name"] = user["Name"]
            session["user_role"] = user["Role"] if "Role" in user.keys() else "User"

            flash("Login successful!", "success")

            if session.get("user_role") == "Admin":
                return redirect(url_for("admin_dashboard"))

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


# =========================================================
# DASHBOARD
# =========================================================
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    connection = get_db_connection()

    my_recipes = connection.execute(
        """
        SELECT Recipes.RecipeID, Recipes.Title, Recipes.CookingTime, Recipes.Difficulty
        FROM Recipes
        WHERE Recipes.UserID = ?
        ORDER BY Recipes.CreatedAt DESC
        LIMIT 5
        """,
        (user_id,)
    ).fetchall()

    favorite_recipes = connection.execute(
        """
        SELECT Recipes.RecipeID, Recipes.Title, Recipes.CookingTime, Recipes.Difficulty
        FROM Favorites
        JOIN Recipes ON Favorites.RecipeID = Recipes.RecipeID
        WHERE Favorites.UserID = ?
        ORDER BY Favorites.CreatedAt DESC
        LIMIT 5
        """,
        (user_id,)
    ).fetchall()

    recent_searches = connection.execute(
        """
        SELECT SearchText, SearchDate
        FROM Search_History
        WHERE UserID = ?
        ORDER BY SearchDate DESC
        LIMIT 5
        """,
        (user_id,)
    ).fetchall()

    total_recipes = connection.execute(
        "SELECT COUNT(*) AS count FROM Recipes WHERE UserID = ?", (user_id,)
    ).fetchone()["count"]

    total_favorites = connection.execute(
        "SELECT COUNT(*) AS count FROM Favorites WHERE UserID = ?", (user_id,)
    ).fetchone()["count"]

    total_ratings = connection.execute(
        "SELECT COUNT(*) AS count FROM Ratings WHERE UserID = ?", (user_id,)
    ).fetchone()["count"]

    total_comments = connection.execute(
        "SELECT COUNT(*) AS count FROM Comments WHERE UserID = ?", (user_id,)
    ).fetchone()["count"]

    total_shopping_lists = connection.execute(
        "SELECT COUNT(*) AS count FROM Shopping_Lists WHERE UserID = ?", (user_id,)
    ).fetchone()["count"]

    connection.close()

    return render_template(
        "dashboard.html",
        my_recipes=my_recipes,
        favorite_recipes=favorite_recipes,
        recent_searches=recent_searches,
        total_recipes=total_recipes,
        total_favorites=total_favorites,
        total_ratings=total_ratings,
        total_comments=total_comments,
        total_shopping_lists=total_shopping_lists
    )


# =========================================================
# LOGOUT
# =========================================================
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("login"))


# =========================================================
# VIEW ALL RECIPES (WITH SEARCH & FILTER)
# =========================================================
@app.route("/recipes")
def recipes():
    if "user_id" not in session:
        return redirect(url_for("login"))

    search = request.args.get("search", "").strip()
    meal_type_id = request.args.get("meal_type_id", "")
    cuisine_id = request.args.get("cuisine_id", "")
    difficulty = request.args.get("difficulty", "")
    max_time = request.args.get("max_time", "")
    ingredient_id = request.args.get("ingredient_id", "")

    connection = get_db_connection()

    meal_types = connection.execute("SELECT * FROM Meal_Types ORDER BY Name").fetchall()
    cuisines = connection.execute("SELECT * FROM Cuisines ORDER BY Name").fetchall()
    ingredients = connection.execute("SELECT * FROM Ingredients ORDER BY Name").fetchall()

    query = """
        SELECT DISTINCT
            Recipes.RecipeID,
            Recipes.Title,
            Recipes.Description,
            Recipes.CookingTime,
            Recipes.Difficulty,
            Recipes.ImageURL,
            Meal_Types.Name AS MealType,
            Cuisines.Name AS Cuisine,
            Users.Name AS Creator
        FROM Recipes
        JOIN Meal_Types ON Recipes.MealTypeID = Meal_Types.MealTypeID
        JOIN Cuisines ON Recipes.CuisineID = Cuisines.CuisineID
        JOIN Users ON Recipes.UserID = Users.UserID
        LEFT JOIN Recipe_Ingredients ON Recipes.RecipeID = Recipe_Ingredients.RecipeID
        LEFT JOIN Ingredients ON Recipe_Ingredients.IngredientID = Ingredients.IngredientID
    """

    conditions = []
    parameters = []

    if search:
        conditions.append("(Recipes.Title LIKE ? OR Ingredients.Name LIKE ?)")
        search_param = f"%{search}%"
        parameters.extend([search_param, search_param])

    if meal_type_id:
        conditions.append("Recipes.MealTypeID = ?")
        parameters.append(meal_type_id)

    if cuisine_id:
        conditions.append("Recipes.CuisineID = ?")
        parameters.append(cuisine_id)

    if difficulty:
        conditions.append("Recipes.Difficulty = ?")
        parameters.append(difficulty)

    if max_time:
        conditions.append("Recipes.CookingTime <= ?")
        parameters.append(max_time)

    if ingredient_id:
        conditions.append("Recipe_Ingredients.IngredientID = ?")
        parameters.append(ingredient_id)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY Recipes.CreatedAt DESC"

    recipes_list = connection.execute(query, parameters).fetchall()

    if search:
        connection.execute(
            "INSERT INTO Search_History (UserID, SearchText) VALUES (?, ?)",
            (session["user_id"], search)
        )
        connection.commit()

    connection.close()

    return render_template(
        "recipes.html",
        recipes=recipes_list,
        meal_types=meal_types,
        cuisines=cuisines,
        ingredients=ingredients,
        selected_search=search,
        selected_meal_type=meal_type_id,
        selected_cuisine=cuisine_id,
        selected_difficulty=difficulty,
        selected_max_time=max_time,
        selected_ingredient_id=ingredient_id
    )


# =========================================================
# VIEW USER'S OWN RECIPES (MY RECIPES)
# =========================================================
@app.route("/my-recipes")
def my_recipes():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    connection = get_db_connection()

    query = """
        SELECT 
            Recipes.RecipeID,
            Recipes.Title,
            Recipes.Description,
            Recipes.CookingTime,
            Recipes.Difficulty,
            Recipes.ImageURL,
            Meal_Types.Name AS MealType,
            Cuisines.Name AS Cuisine,
            Users.Name AS Creator
        FROM Recipes
        JOIN Meal_Types ON Recipes.MealTypeID = Meal_Types.MealTypeID
        JOIN Cuisines ON Recipes.CuisineID = Cuisines.CuisineID
        JOIN Users ON Recipes.UserID = Users.UserID
        WHERE Recipes.UserID = ?
        ORDER BY Recipes.CreatedAt DESC
    """

    my_recipes_list = connection.execute(query, (user_id,)).fetchall()
    connection.close()

    return render_template("my_recipes.html", recipes=my_recipes_list)


# =========================================================
# ADD RECIPE
# =========================================================
@app.route("/add-recipe", methods=["GET", "POST"])
def add_recipe():
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        cooking_time = request.form.get("cooking_time")
        difficulty = request.form.get("difficulty")
        instructions = request.form.get("instructions", "").strip()
        meal_type_id = request.form.get("meal_type_id")
        cuisine_id = request.form.get("cuisine_id")
        spice_level = request.form.get("spice_level", "").strip() or None
        diet_type = request.form.get("diet_type", "").strip() or None

        def parse_float(value):
            try:
                return float(value) if value and value.strip() else 0.0
            except ValueError:
                return 0.0

        calories = parse_float(request.form.get("calories"))
        protein = parse_float(request.form.get("protein"))
        carbohydrates = parse_float(request.form.get("carbohydrates"))
        fat = parse_float(request.form.get("fat"))
        fiber = parse_float(request.form.get("fiber"))

        image_url = request.form.get("image_url", "").strip()
        image_file = request.files.get("image_file")

        if image_file and image_file.filename != "":
            try:
                uploaded_url = save_uploaded_image(image_file)
                if uploaded_url:
                    image_url = uploaded_url
            except ValueError as exc:
                connection.close()
                flash(str(exc))
                return redirect(url_for("add_recipe"))

        try:
            cooking_time_value = int(cooking_time)
            if cooking_time_value <= 0:
                raise ValueError
        except (TypeError, ValueError):
            connection.close()
            flash("Cooking time must be a positive number.")
            return redirect(url_for("add_recipe"))

        if not title or not instructions or not meal_type_id or not cuisine_id:
            connection.close()
            flash("Please fill all required fields.")
            return redirect(url_for("add_recipe"))

        cursor = connection.execute(
            """
            INSERT INTO Recipes 
            (UserID, MealTypeID, CuisineID, Title, Description, CookingTime, Difficulty, SpiceLevel, DietType, Instructions, ImageURL)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                meal_type_id,
                cuisine_id,
                title,
                description,
                cooking_time_value,
                difficulty,
                spice_level,
                diet_type,
                instructions,
                image_url,
            ),
        )
        recipe_id = cursor.lastrowid

        connection.execute(
            """
            INSERT INTO Nutrition (RecipeID, Calories, Protein, Carbohydrates, Fat, Fiber)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (recipe_id, calories, protein, carbohydrates, fat, fiber),
        )

        selected_ingredients = request.form.getlist("ingredients")
        for ing_id in selected_ingredients:
            quantity = request.form.get(f"quantity_{ing_id}", "").strip()
            unit = request.form.get(f"unit_{ing_id}", "").strip()

            connection.execute(
                "INSERT INTO Recipe_Ingredients (RecipeID, IngredientID, Quantity, Unit) VALUES (?, ?, ?, ?)",
                (recipe_id, ing_id, quantity if quantity else "As needed", unit),
            )

        connection.commit()
        connection.close()

        flash("Recipe added successfully!")
        return redirect(url_for("recipe_detail", recipe_id=recipe_id))

    meal_types = connection.execute("SELECT * FROM Meal_Types ORDER BY Name").fetchall()
    cuisines = connection.execute("SELECT * FROM Cuisines ORDER BY Name").fetchall()
    ingredients = connection.execute("SELECT * FROM Ingredients ORDER BY Name").fetchall()
    connection.close()

    return render_template(
        "add_recipe.html",
        meal_types=meal_types,
        cuisines=cuisines,
        ingredients=ingredients,
    )


# =========================================================
# ADD NEW INGREDIENT
# =========================================================
@app.route("/add-ingredient", methods=["GET", "POST"])
def add_ingredient():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form["name"].strip()

        if not name:
            flash("Ingredient name cannot be empty.")
            return redirect(url_for("add_ingredient"))

        connection = get_db_connection()
        existing = connection.execute(
            "SELECT IngredientID FROM Ingredients WHERE LOWER(Name) = ?", (name.lower(),)
        ).fetchone()

        if existing:
            connection.close()
            flash("Ingredient already exists.")
            return redirect(url_for("add_ingredient"))

        connection.execute("INSERT INTO Ingredients (Name) VALUES (?)", (name,))
        connection.commit()
        connection.close()

        flash("New ingredient added successfully!")
        return redirect(url_for("add_recipe"))

    return render_template("add_ingredient.html")


# =========================================================
# RECIPE DETAILS
# =========================================================
@app.route("/recipe/<int:recipe_id>")
def recipe_detail(recipe_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    recipe = connection.execute(
        """
        SELECT Recipes.*, Meal_Types.Name AS MealType, Cuisines.Name AS Cuisine, Users.Name AS Creator
        FROM Recipes
        JOIN Meal_Types ON Recipes.MealTypeID = Meal_Types.MealTypeID
        JOIN Cuisines ON Recipes.CuisineID = Cuisines.CuisineID
        JOIN Users ON Recipes.UserID = Users.UserID
        WHERE Recipes.RecipeID = ?
        """,
        (recipe_id,)
    ).fetchone()

    if not recipe:
        connection.close()
        flash("Recipe not found.")
        return redirect(url_for("recipes"))

    recipe_ingredients = connection.execute(
        """
        SELECT Ingredients.IngredientID, Ingredients.Name, Recipe_Ingredients.Quantity, Recipe_Ingredients.Unit
        FROM Recipe_Ingredients
        JOIN Ingredients ON Recipe_Ingredients.IngredientID = Ingredients.IngredientID
        WHERE Recipe_Ingredients.RecipeID = ?
        ORDER BY Ingredients.Name
        """,
        (recipe_id,)
    ).fetchall()

    nutrition = connection.execute(
        "SELECT * FROM Nutrition WHERE RecipeID = ?", (recipe_id,)
    ).fetchone()

    comments = connection.execute(
        """
        SELECT Comments.CommentText, Comments.CreatedAt, Users.Name AS UserName
        FROM Comments
        JOIN Users ON Comments.UserID = Users.UserID
        WHERE Comments.RecipeID = ?
        ORDER BY Comments.CreatedAt DESC
        """,
        (recipe_id,)
    ).fetchall()

    favorite = connection.execute(
        "SELECT FavoriteID FROM Favorites WHERE UserID = ? AND RecipeID = ?",
        (session["user_id"], recipe_id)
    ).fetchone()

    ratings = connection.execute(
        """
        SELECT Ratings.Rating, Ratings.Review, Ratings.CreatedAt, Users.Name
        FROM Ratings
        JOIN Users ON Ratings.UserID = Users.UserID
        WHERE Ratings.RecipeID = ?
        ORDER BY Ratings.CreatedAt DESC
        """,
        (recipe_id,)
    ).fetchall()

    avg_row = connection.execute(
        "SELECT AVG(Rating) AS AverageRating FROM Ratings WHERE RecipeID = ?",
        (recipe_id,)
    ).fetchone()

    connection.close()

    average_rating = avg_row["AverageRating"] if avg_row and avg_row["AverageRating"] is not None else None

    available_ingredients = set(int(x) for x in session.get("available_ingredients", []))
    matched_count = 0
    missing_count = 0

    if available_ingredients:
        recipe_ingredient_ids = {row["IngredientID"] for row in recipe_ingredients}
        matched_count = len(recipe_ingredient_ids & available_ingredients)
        missing_count = len(recipe_ingredient_ids - available_ingredients)

    return render_template(
        "recipe_detail.html",
        recipe=recipe,
        recipe_ingredients=recipe_ingredients,
        ingredients=recipe_ingredients,
        nutrition=nutrition,
        comments=comments,
        is_favorite=bool(favorite),
        ratings=ratings,
        average_rating=average_rating,
        available_ingredients=available_ingredients,
        matched_count=matched_count,
        missing_count=missing_count
    )


# =========================================================
# EDIT RECIPE
# =========================================================
@app.route("/edit-recipe/<int:recipe_id>", methods=["GET", "POST"])
def edit_recipe(recipe_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    recipe = connection.execute(
        "SELECT * FROM Recipes WHERE RecipeID = ?", (recipe_id,)
    ).fetchone()

    if not recipe:
        connection.close()
        flash("Recipe not found.")
        return redirect(url_for("recipes"))

    if recipe["UserID"] != session["user_id"]:
        connection.close()
        flash("You are not allowed to edit this recipe.")
        return redirect(url_for("recipe_detail", recipe_id=recipe_id))

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        meal_type_id = request.form.get("meal_type_id")
        cuisine_id = request.form.get("cuisine_id")
        cooking_time = request.form.get("cooking_time")
        difficulty = request.form.get("difficulty")
        spice_level = request.form.get("spice_level")
        diet_type = request.form.get("diet_type")
        instructions = request.form.get("instructions")
        image_url = request.form.get("image_url")

        connection.execute(
            """
            UPDATE Recipes
            SET Title = ?, Description = ?, MealTypeID = ?, CuisineID = ?, CookingTime = ?, Difficulty = ?, Instructions = ?, ImageURL = ?, SpiceLevel = ?, DietType = ?
            WHERE RecipeID = ?
            """,
            (
                title, description, meal_type_id, cuisine_id, cooking_time,
                difficulty, instructions, image_url, spice_level, diet_type, recipe_id
            )
        )

        selected_ingredients = request.form.getlist("ingredients")
        connection.execute("DELETE FROM Recipe_Ingredients WHERE RecipeID = ?", (recipe_id,))

        for ingredient_id in selected_ingredients:
            quantity = request.form.get(f"quantity_{ingredient_id}", "").strip()
            unit = request.form.get(f"unit_{ingredient_id}", "").strip()
            connection.execute(
                "INSERT INTO Recipe_Ingredients (RecipeID, IngredientID, Quantity, Unit) VALUES (?, ?, ?, ?)",
                (recipe_id, ingredient_id, quantity if quantity else "As needed", unit)
            )

        calories = request.form.get("calories")
        protein = request.form.get("protein")
        carbohydrates = request.form.get("carbohydrates")
        fat = request.form.get("fat")
        fiber = request.form.get("fiber")

        nutrition_exists = connection.execute(
            "SELECT NutritionID FROM Nutrition WHERE RecipeID = ?", (recipe_id,)
        ).fetchone()

        if nutrition_exists:
            connection.execute(
                """
                UPDATE Nutrition
                SET Calories = ?, Protein = ?, Carbohydrates = ?, Fat = ?, Fiber = ?
                WHERE RecipeID = ?
                """,
                (calories or 0, protein or 0, carbohydrates or 0, fat or 0, fiber or 0, recipe_id)
            )
        else:
            connection.execute(
                """
                INSERT INTO Nutrition (RecipeID, Calories, Protein, Carbohydrates, Fat, Fiber)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (recipe_id, calories or 0, protein or 0, carbohydrates or 0, fat or 0, fiber or 0)
            )

        connection.commit()
        connection.close()

        flash("Recipe updated successfully!")
        return redirect(url_for("recipe_detail", recipe_id=recipe_id))

    meal_types = connection.execute("SELECT * FROM Meal_Types ORDER BY Name").fetchall()
    cuisines = connection.execute("SELECT * FROM Cuisines ORDER BY Name").fetchall()
    ingredients = connection.execute("SELECT * FROM Ingredients ORDER BY Name").fetchall()

    existing_ingredients = connection.execute(
        "SELECT IngredientID FROM Recipe_Ingredients WHERE RecipeID = ?", (recipe_id,)
    ).fetchall()
    existing_ingredient_ids = {row["IngredientID"] for row in existing_ingredients}

    nutrition = connection.execute(
        "SELECT * FROM Nutrition WHERE RecipeID = ?", (recipe_id,)
    ).fetchone()

    connection.close()

    return render_template(
        "edit_recipe.html",
        recipe=recipe,
        meal_types=meal_types,
        cuisines=cuisines,
        ingredients=ingredients,
        existing_ingredient_ids=existing_ingredient_ids,
        nutrition=nutrition
    )


# =========================================================
# DELETE RECIPE
# =========================================================
@app.route("/delete-recipe/<int:recipe_id>", methods=["POST"])
def delete_recipe(recipe_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    recipe = connection.execute("SELECT UserID FROM Recipes WHERE RecipeID = ?", (recipe_id,)).fetchone()

    if recipe is None:
        connection.close()
        flash("Recipe not found.")
        return redirect(url_for("recipes"))

    if recipe["UserID"] != session["user_id"]:
        connection.close()
        flash("You can only delete your own recipes.")
        return redirect(url_for("recipes"))

    connection.execute("DELETE FROM Recipe_Ingredients WHERE RecipeID = ?", (recipe_id,))
    connection.execute("DELETE FROM Favorites WHERE RecipeID = ?", (recipe_id,))
    connection.execute("DELETE FROM Ratings WHERE RecipeID = ?", (recipe_id,))
    connection.execute("DELETE FROM Comments WHERE RecipeID = ?", (recipe_id,))
    connection.execute("DELETE FROM Recipes WHERE RecipeID = ?", (recipe_id,))
    
    connection.commit()
    connection.close()

    flash("Recipe deleted successfully.")
    return redirect(url_for("recipes"))


# =========================================================
# ADD / REMOVE FAVORITE
# =========================================================
@app.route("/favorite/<int:recipe_id>", methods=["POST"])
def favorite_recipe(recipe_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    recipe_exists = connection.execute(
        "SELECT RecipeID FROM Recipes WHERE RecipeID = ?", (recipe_id,)
    ).fetchone()

    if recipe_exists is None:
        connection.close()
        flash("Recipe not found.")
        return redirect(url_for("recipes"))

    existing = connection.execute(
        "SELECT FavoriteID FROM Favorites WHERE UserID = ? AND RecipeID = ?",
        (session["user_id"], recipe_id)
    ).fetchone()

    if existing:
        connection.execute("DELETE FROM Favorites WHERE FavoriteID = ?", (existing["FavoriteID"],))
        flash("Recipe removed from favorites.")
    else:
        connection.execute(
            "INSERT INTO Favorites (UserID, RecipeID) VALUES (?, ?)",
            (session["user_id"], recipe_id)
        )
        flash("Recipe added to favorites.")

    connection.commit()
    connection.close()

    return redirect(url_for("recipe_detail", recipe_id=recipe_id))


# =========================================================
# ADD / UPDATE RATING
# =========================================================
@app.route("/rate/<int:recipe_id>", methods=["POST"])
def rate_recipe(recipe_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    rating = request.form.get("rating")
    review = request.form.get("review", "").strip()

    try:
        rating = int(rating)
    except (TypeError, ValueError):
        flash("Invalid rating.")
        return redirect(url_for("recipe_detail", recipe_id=recipe_id))

    if rating < 1 or rating > 5:
        flash("Rating must be between 1 and 5.")
        return redirect(url_for("recipe_detail", recipe_id=recipe_id))

    connection = get_db_connection()

    recipe_exists = connection.execute(
        "SELECT RecipeID FROM Recipes WHERE RecipeID = ?", (recipe_id,)
    ).fetchone()

    if recipe_exists is None:
        connection.close()
        flash("Recipe not found.")
        return redirect(url_for("recipes"))

    existing = connection.execute(
        "SELECT RatingID FROM Ratings WHERE UserID = ? AND RecipeID = ?",
        (session["user_id"], recipe_id)
    ).fetchone()

    if existing:
        connection.execute(
            """
            UPDATE Ratings
            SET Rating = ?, Review = ?, CreatedAt = CURRENT_TIMESTAMP
            WHERE RatingID = ?
            """,
            (rating, review, existing["RatingID"])
        )
        flash("Your rating has been updated.")
    else:
        connection.execute(
            "INSERT INTO Ratings (UserID, RecipeID, Rating, Review) VALUES (?, ?, ?, ?)",
            (session["user_id"], recipe_id, rating, review)
        )
        flash("Thank you for rating this recipe!")

    connection.commit()
    connection.close()

    return redirect(url_for("recipe_detail", recipe_id=recipe_id))


# =========================================================
# ADD COMMENT
# =========================================================
@app.route("/comment/<int:recipe_id>", methods=["POST"])
def add_comment(recipe_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    comment_text = request.form.get("comment", "").strip()

    if not comment_text:
        flash("Comment cannot be empty.")
        return redirect(url_for("recipe_detail", recipe_id=recipe_id))

    connection = get_db_connection()

    recipe_exists = connection.execute(
        "SELECT RecipeID FROM Recipes WHERE RecipeID = ?", (recipe_id,)
    ).fetchone()

    if recipe_exists is None:
        connection.close()
        flash("Recipe not found.")
        return redirect(url_for("recipes"))

    connection.execute(
        "INSERT INTO Comments (UserID, RecipeID, CommentText) VALUES (?, ?, ?)",
        (session["user_id"], recipe_id, comment_text)
    )

    connection.commit()
    connection.close()

    flash("Comment added successfully.")
    return redirect(url_for("recipe_detail", recipe_id=recipe_id))


# =========================================================
# VIEW FAVORITE RECIPES
# =========================================================
@app.route("/favorites")
def favorites():
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    query = """
        SELECT 
            Recipes.RecipeID,
            Recipes.Title,
            Recipes.Description,
            Recipes.CookingTime,
            Recipes.Difficulty,
            Recipes.ImageURL,
            Meal_Types.Name AS MealType,
            Cuisines.Name AS Cuisine,
            Users.Name AS Creator
        FROM Favorites
        JOIN Recipes ON Favorites.RecipeID = Recipes.RecipeID
        JOIN Meal_Types ON Recipes.MealTypeID = Meal_Types.MealTypeID
        JOIN Cuisines ON Recipes.CuisineID = Cuisines.CuisineID
        JOIN Users ON Recipes.UserID = Users.UserID
        WHERE Favorites.UserID = ?
        ORDER BY Favorites.CreatedAt DESC
    """
    fav_recipes = connection.execute(query, (session["user_id"],)).fetchall()
    connection.close()

    return render_template("favorites.html", recipes=fav_recipes)


# =========================================================
# USER PREFERENCES ROUTE
# =========================================================
@app.route("/preferences", methods=["GET", "POST"])
def preferences():
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    user_id = session["user_id"]

    if request.method == "POST":
        spice_level = request.form.get("spice_level", "Medium")
        diet_type = request.form.get("diet_type", "Regular")
        
        try:
            max_cooking_time = int(request.form.get("max_cooking_time", 30))
        except (ValueError, TypeError):
            max_cooking_time = 30

        difficulty = request.form.get("difficulty", "Easy")
        calorie_preference = request.form.get("calorie_preference", "Moderate")

        existing = connection.execute(
            "SELECT PreferenceID FROM User_Preferences WHERE UserID = ?", (user_id,)
        ).fetchone()

        if existing:
            connection.execute(
                """
                UPDATE User_Preferences
                SET SpiceLevel = ?, DietType = ?, MaxCookingTime = ?, DifficultyPreference = ?, CaloriePreference = ?
                WHERE UserID = ?
                """,
                (spice_level, diet_type, max_cooking_time, difficulty, calorie_preference, user_id)
            )
        else:
            connection.execute(
                """
                INSERT INTO User_Preferences (UserID, SpiceLevel, DietType, MaxCookingTime, DifficultyPreference, CaloriePreference)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, spice_level, diet_type, max_cooking_time, difficulty, calorie_preference)
            )

        connection.commit()
        connection.close()

        flash("Preferences saved successfully!")
        return redirect(url_for("preferences"))

    user_preferences = connection.execute(
        "SELECT * FROM User_Preferences WHERE UserID = ?", (user_id,)
    ).fetchone()

    connection.close()

    return render_template("preferences.html", preferences=user_preferences)


# =========================================================
# SMART RECOMMENDATIONS
# =========================================================
@app.route("/recommendations")
def recommendations():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    connection = get_db_connection()

    selected_meal_type = request.args.get("meal_type_id", "").strip()
    selected_cuisine = request.args.get("cuisine_id", "").strip()
    selected_difficulty = request.args.get("difficulty", "").strip()
    selected_max_time = request.args.get("max_time", "").strip()

    preferences = connection.execute(
        "SELECT * FROM User_Preferences WHERE UserID = ?", (user_id,)
    ).fetchone()

    available_ids = set(int(x) for x in session.get("available_ingredients", []))

    meal_types = connection.execute("SELECT * FROM Meal_Types ORDER BY Name").fetchall()
    cuisines = connection.execute("SELECT * FROM Cuisines ORDER BY Name").fetchall()

    recipes = connection.execute(
        """
        SELECT Recipes.*, Meal_Types.Name AS MealType, Cuisines.Name AS Cuisine
        FROM Recipes
        JOIN Meal_Types ON Recipes.MealTypeID = Meal_Types.MealTypeID
        JOIN Cuisines ON Recipes.CuisineID = Cuisines.CuisineID
        ORDER BY Recipes.CreatedAt DESC
        """
    ).fetchall()

    search_history = connection.execute(
        "SELECT SearchText FROM Search_History WHERE UserID = ? ORDER BY SearchDate DESC LIMIT 20",
        (user_id,)
    ).fetchall()
    search_keywords = [row["SearchText"].lower() for row in search_history]

    recommended_recipes = []

    for recipe in recipes:
        if selected_meal_type and str(recipe["MealTypeID"]) != selected_meal_type:
            continue
        if selected_cuisine and str(recipe["CuisineID"]) != selected_cuisine:
            continue
        if selected_difficulty and recipe["Difficulty"] != selected_difficulty:
            continue
        if selected_max_time:
            try:
                if recipe["CookingTime"] > int(selected_max_time):
                    continue
            except ValueError:
                pass

        score = 0

        recipe_ingredients = connection.execute(
            "SELECT IngredientID FROM Recipe_Ingredients WHERE RecipeID = ?", (recipe["RecipeID"],)
        ).fetchall()
        recipe_ingredient_ids = {row["IngredientID"] for row in recipe_ingredients}

        if recipe_ingredient_ids:
            matched_ingredients = recipe_ingredient_ids & available_ids
            ingredient_percentage = len(matched_ingredients) / len(recipe_ingredient_ids)
            score += ingredient_percentage * 35
        else:
            ingredient_percentage = 0

        if selected_meal_type and str(recipe["MealTypeID"]) == selected_meal_type:
            score += 10
        if selected_cuisine and str(recipe["CuisineID"]) == selected_cuisine:
            score += 10

        if preferences:
            max_time_pref = preferences["MaxCookingTime"]
            if max_time_pref:
                try:
                    if recipe["CookingTime"] <= int(max_time_pref):
                        score += 10
                except (TypeError, ValueError):
                    pass

            if recipe["Difficulty"] == preferences["DifficultyPreference"]:
                score += 8
            if recipe["SpiceLevel"] == preferences["SpiceLevel"]:
                score += 8
            if recipe["DietType"] == preferences["DietType"]:
                score += 5

        rating = connection.execute(
            "SELECT AVG(Rating) AS AverageRating FROM Ratings WHERE RecipeID = ?", (recipe["RecipeID"],)
        ).fetchone()
        average_rating = rating["AverageRating"] if rating and rating["AverageRating"] else 0
        score += (average_rating / 5) * 5

        history_score = 0
        for keyword in search_keywords:
            if not keyword:
                continue
            if keyword in recipe["Title"].lower():
                history_score = 9
                break

            ingredient_match = connection.execute(
                """
                SELECT Ingredients.Name FROM Recipe_Ingredients
                JOIN Ingredients ON Recipe_Ingredients.IngredientID = Ingredients.IngredientID
                WHERE Recipe_Ingredients.RecipeID = ? AND LOWER(Ingredients.Name) LIKE ?
                """,
                (recipe["RecipeID"], f"%{keyword}%")
            ).fetchone()

            if ingredient_match:
                history_score = 9
                break

        score += history_score

        recommended_recipes.append({
            "recipe": recipe,
            "score": round(score, 1),
            "ingredient_percentage": round(ingredient_percentage * 100, 1),
            "average_rating": round(average_rating, 1)
        })

    recommended_recipes.sort(key=lambda x: x["score"], reverse=True)
    connection.close()

    return render_template(
        "recommendations.html",
        recommendations=recommended_recipes,
        preferences=preferences,
        meal_types=meal_types,
        cuisines=cuisines,
        selected_meal_type=selected_meal_type,
        selected_cuisine=selected_cuisine,
        selected_difficulty=selected_difficulty,
        selected_max_time=selected_max_time
    )


# =========================================================
# MY AVAILABLE INGREDIENTS
# =========================================================
@app.route("/my-ingredients", methods=["GET", "POST"])
def my_ingredients():
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    if request.method == "POST":
        selected_ingredients = request.form.getlist("ingredients")

        if not selected_ingredients:
            connection.close()
            flash("Please select at least one ingredient.")
            return redirect(url_for("my_ingredients"))

        try:
            session["available_ingredients"] = [int(x) for x in selected_ingredients]
        except (TypeError, ValueError):
            connection.close()
            flash("Invalid ingredient selection.")
            return redirect(url_for("my_ingredients"))

        connection.close()
        return redirect(url_for("ingredient_recommendations"))

    ingredients = connection.execute("SELECT * FROM Ingredients ORDER BY Name").fetchall()
    connection.close()

    return render_template("my_ingredients.html", ingredients=ingredients)


# =========================================================
# INGREDIENT-BASED RECOMMENDATIONS
# =========================================================
@app.route("/ingredient-recommendations")
def ingredient_recommendations():
    if "user_id" not in session:
        return redirect(url_for("login"))

    selected_ids = session.get("available_ingredients", [])

    try:
        selected_ids = list(dict.fromkeys(int(i) for i in selected_ids))
    except (TypeError, ValueError):
        selected_ids = []

    if not selected_ids:
        flash("Please select your available ingredients first.")
        return redirect(url_for("my_ingredients"))

    connection = get_db_connection()
    session["available_ingredient_ids"] = selected_ids

    placeholders = ",".join(["?"] * len(selected_ids))
    selected_ingredients = connection.execute(
        f"SELECT IngredientID, Name FROM Ingredients WHERE IngredientID IN ({placeholders}) ORDER BY Name",
        selected_ids
    ).fetchall()

    query = f"""
        SELECT
            Recipes.RecipeID,
            Recipes.Title,
            Recipes.Description,
            Recipes.CookingTime,
            Recipes.Difficulty,
            Recipes.ImageURL,
            Meal_Types.Name AS MealType,
            Cuisines.Name AS Cuisine,
            COUNT(DISTINCT Recipe_Ingredients.IngredientID) AS MatchedCount,
            (SELECT COUNT(*) FROM Recipe_Ingredients RI2 WHERE RI2.RecipeID = Recipes.RecipeID) AS TotalIngredients
        FROM Recipes
        LEFT JOIN Meal_Types ON Recipes.MealTypeID = Meal_Types.MealTypeID
        LEFT JOIN Cuisines ON Recipes.CuisineID = Cuisines.CuisineID
        JOIN Recipe_Ingredients ON Recipes.RecipeID = Recipe_Ingredients.RecipeID
        WHERE Recipe_Ingredients.IngredientID IN ({placeholders})
        GROUP BY Recipes.RecipeID
        ORDER BY MatchedCount DESC, Recipes.CreatedAt DESC
    """

    matched_recipes = connection.execute(query, selected_ids).fetchall()
    results = []

    for r in matched_recipes:
        recipe_id = r["RecipeID"]

        all_recipe_ingredients = connection.execute(
            """
            SELECT Ingredients.IngredientID, Ingredients.Name, Recipe_Ingredients.Quantity, Recipe_Ingredients.Unit
            FROM Recipe_Ingredients
            JOIN Ingredients ON Recipe_Ingredients.IngredientID = Ingredients.IngredientID
            WHERE Recipe_Ingredients.RecipeID = ?
            """,
            (recipe_id,)
        ).fetchall()

        missing_ingredients = []
        for ing in all_recipe_ingredients:
            if ing["IngredientID"] not in selected_ids:
                missing_ingredients.append({
                    "IngredientID": ing["IngredientID"],
                    "Name": ing["Name"],
                    "Quantity": ing["Quantity"],
                    "Unit": ing["Unit"]
                })

        total = r["TotalIngredients"]
        matched = r["MatchedCount"]
        match_percentage = round((matched / total) * 100) if total > 0 else 0

        results.append({
            "recipe": {
                "RecipeID": r["RecipeID"],
                "Title": r["Title"],
                "Description": r["Description"],
                "CookingTime": r["CookingTime"],
                "Difficulty": r["Difficulty"],
                "ImageURL": r["ImageURL"],
                "MealType": r["MealType"],
                "Cuisine": r["Cuisine"]
            },
            "matched_count": matched,
            "total_ingredients": total,
            "match_percentage": match_percentage,
            "missing": missing_ingredients
        })

    connection.close()

    return render_template(
        "ingredient_recommendations.html",
        selected_ingredients=selected_ingredients,
        results=results
    )


# =========================================================
# CREATE SHOPPING LIST FROM MISSING INGREDIENTS
# =========================================================
@app.route("/create-shopping-list/<int:recipe_id>")
def create_shopping_list(recipe_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    user_id = session["user_id"]

    recipe = connection.execute(
        "SELECT RecipeID, Title FROM Recipes WHERE RecipeID = ?", (recipe_id,)
    ).fetchone()

    if recipe is None:
        connection.close()
        flash("Recipe not found.")
        return redirect(url_for("recipes"))

    available_ids = session.get("available_ingredients", [])
    try:
        available_ids = [int(i) for i in available_ids]
    except (TypeError, ValueError):
        available_ids = []

    cursor = connection.execute(
        "INSERT INTO Shopping_Lists (UserID, ListName) VALUES (?, ?)",
        (user_id, f"Missing Ingredients - {recipe['Title']}")
    )
    shopping_list_id = cursor.lastrowid

    recipe_ingredients = connection.execute(
        "SELECT IngredientID, Quantity, Unit FROM Recipe_Ingredients WHERE RecipeID = ?",
        (recipe_id,)
    ).fetchall()

    added_count = 0

    for ingredient in recipe_ingredients:
        if ingredient["IngredientID"] in available_ids:
            continue

        connection.execute(
            """
            INSERT INTO Shopping_List_Items (ShoppingListID, IngredientID, Quantity, Unit)
            VALUES (?, ?, ?, ?)
            """,
            (shopping_list_id, ingredient["IngredientID"], ingredient["Quantity"], ingredient["Unit"])
        )
        added_count += 1

    if added_count == 0:
        connection.execute(
            "DELETE FROM Shopping_Lists WHERE ShoppingListID = ?", (shopping_list_id,)
        )
        connection.commit()
        connection.close()
        flash("You already have all ingredients for this recipe.")
        return redirect(url_for("ingredient_recommendations"))

    connection.commit()
    connection.close()

    flash("Shopping list created successfully!")
    return redirect(url_for("shopping_list"))


# =========================================================
# ADD MISSING INGREDIENTS TO SHOPPING LIST (Unified using Shopping_Lists & Items)
# =========================================================
@app.route("/add-missing-to-shopping-list/<int:recipe_id>", methods=["POST"])
def add_missing_to_shopping_list(recipe_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user_id = session["user_id"]
    raw_available = session.get("available_ingredients", [])
    available_ingredients = [int(x) for x in raw_available]
    
    connection = get_db_connection()

    recipe = connection.execute(
        "SELECT Title FROM Recipes WHERE RecipeID = ?", (recipe_id,)
    ).fetchone()

    if not recipe:
        connection.close()
        flash("Recipe not found.")
        return redirect(url_for("recipes"))

    # Find or create a default generic shopping list for missing items
    list_name = f"Quick Missing Items"
    shopping_list = connection.execute(
        "SELECT ShoppingListID FROM Shopping_Lists WHERE UserID = ? AND ListName = ?",
        (user_id, list_name)
    ).fetchone()

    if shopping_list:
        shopping_list_id = shopping_list["ShoppingListID"]
    else:
        cursor = connection.execute(
            "INSERT INTO Shopping_Lists (UserID, ListName) VALUES (?, ?)",
            (user_id, list_name)
        )
        shopping_list_id = cursor.lastrowid

    recipe_ingredients = connection.execute(
        "SELECT IngredientID, Quantity, Unit FROM Recipe_Ingredients WHERE RecipeID = ?",
        (recipe_id,)
    ).fetchall()
    
    for item in recipe_ingredients:
        ing_id = int(item['IngredientID'])
        
        if ing_id not in available_ingredients:
            existing = connection.execute(
                """
                SELECT * FROM Shopping_List_Items 
                WHERE ShoppingListID = ? AND IngredientID = ? AND Status = 'Pending'
                """,
                (shopping_list_id, ing_id)
            ).fetchone()
            
            if existing:
                connection.execute(
                    """
                    UPDATE Shopping_List_Items 
                    SET Quantity = Quantity + ? 
                    WHERE ShoppingListItemID = ?
                    """,
                    (item['Quantity'] if isinstance(item['Quantity'], (int, float)) else 1, existing["ShoppingListItemID"] if "ShoppingListItemID" in existing.keys() else existing[0])
                )
            else:
                connection.execute(
                    """
                    INSERT INTO Shopping_List_Items (ShoppingListID, IngredientID, Quantity, Unit, Status) 
                    VALUES (?, ?, ?, ?, 'Pending')
                    """,
                    (shopping_list_id, ing_id, item['Quantity'], item['Unit'])
                )
            
    connection.commit()
    connection.close()
    
    flash("Missing ingredients added to your shopping list successfully!")
    return redirect(url_for("shopping_list"))


# =========================================================
# SHOPPING LIST ROUTE
# =========================================================
@app.route("/shopping-list")
def shopping_list():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user_id = session["user_id"]
    connection = get_db_connection()
    
    shopping_items = connection.execute(
        """
        SELECT 
            sil.ShoppingListItemID AS ShoppingListID, 
            i.Name, 
            sil.Quantity, 
            sil.Unit,
            sil.Status
        FROM Shopping_List_Items sil
        JOIN Shopping_Lists sl ON sil.ShoppingListID = sl.ShoppingListID
        JOIN Ingredients i ON sil.IngredientID = i.IngredientID
        WHERE sl.UserID = ?
        """,
        (user_id,)
    ).fetchall()
    
    connection.close()
    return render_template("shopping_list.html", items=shopping_items)


# =========================================================
# CLEAR SHOPPING LIST ROUTE
# =========================================================
@app.route("/clear-shopping-list", methods=["POST"])
def clear_shopping_list():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user_id = session["user_id"]
    connection = get_db_connection()
    
    shopping_lists = connection.execute(
        "SELECT ShoppingListID FROM Shopping_Lists WHERE UserID = ?", (user_id,)
    ).fetchall()

    for sl in shopping_lists:
        connection.execute("DELETE FROM Shopping_List_Items WHERE ShoppingListID = ?", (sl["ShoppingListID"],))
    
    connection.execute("DELETE FROM Shopping_Lists WHERE UserID = ?", (user_id,))
    connection.commit()
    connection.close()
    
    flash("Shopping list cleared successfully!")
    return redirect(url_for("shopping_list"))


# =========================================================
# TOGGLE PURCHASED STATUS ROUTE
# =========================================================
@app.route("/toggle-purchased/<int:item_id>", methods=["POST"])
def toggle_purchased(item_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    item = connection.execute(
        "SELECT Status FROM Shopping_List_Items WHERE ShoppingListItemID = ?", (item_id,)
    ).fetchone()

    if item:
        new_status = "Purchased" if item["Status"] != "Purchased" else "Pending"
        connection.execute(
            "UPDATE Shopping_List_Items SET Status = ? WHERE ShoppingListItemID = ?",
            (new_status, item_id),
        )
        connection.commit()

    connection.close()
    return redirect(url_for("shopping_list"))


# =========================================================
# DELETE SHOPPING ITEM ROUTE
# =========================================================
@app.route("/delete-shopping-item/<int:item_id>", methods=["POST"])
def delete_shopping_item(item_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    connection.execute(
        "DELETE FROM Shopping_List_Items WHERE ShoppingListItemID = ?", (item_id,)
    )
    connection.commit()
    connection.close()

    flash("Item deleted successfully!")
    return redirect(url_for("shopping_list"))


# =========================================================
# ADMIN DASHBOARD
# =========================================================
@app.route("/admin")
def admin_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "Admin":
        flash("Access denied. Admin only.")
        return redirect(url_for("dashboard"))

    connection = get_db_connection()

    total_users = connection.execute("SELECT COUNT(*) AS count FROM Users").fetchone()["count"]
    total_recipes = connection.execute("SELECT COUNT(*) AS count FROM Recipes").fetchone()["count"]
    total_ingredients = connection.execute("SELECT COUNT(*) AS count FROM Ingredients").fetchone()["count"]
    total_favorites = connection.execute("SELECT COUNT(*) AS count FROM Favorites").fetchone()["count"]
    total_ratings = connection.execute("SELECT COUNT(*) AS count FROM Ratings").fetchone()["count"]
    total_comments = connection.execute("SELECT COUNT(*) AS count FROM Comments").fetchone()["count"]

    all_recipes = connection.execute(
        """
        SELECT Recipes.*, Users.Name AS Author
        FROM Recipes
        LEFT JOIN Users ON Recipes.UserID = Users.UserID
        ORDER BY Recipes.CreatedAt DESC
        """
    ).fetchall()

    meal_data = connection.execute(
        """
        SELECT Meal_Types.Name AS MealType, COUNT(Recipes.RecipeID) AS Total
        FROM Meal_Types
        LEFT JOIN Recipes ON Meal_Types.MealTypeID = Recipes.MealTypeID
        GROUP BY Meal_Types.MealTypeID
        ORDER BY Total DESC
        """
    ).fetchall()

    cuisine_data = connection.execute(
        """
        SELECT Cuisines.Name AS Cuisine, COUNT(Recipes.RecipeID) AS Total
        FROM Cuisines
        LEFT JOIN Recipes ON Cuisines.CuisineID = Recipes.CuisineID
        GROUP BY Cuisines.CuisineID
        ORDER BY Total DESC
        """
    ).fetchall()

    rating_data = connection.execute(
        """
        SELECT Rating, COUNT(*) AS Total
        FROM Ratings
        GROUP BY Rating
        ORDER BY Rating
        """
    ).fetchall()

    connection.close()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_recipes=total_recipes,
        total_ingredients=total_ingredients,
        total_favorites=total_favorites,
        total_ratings=total_ratings,
        total_comments=total_comments,
        all_recipes=all_recipes,
        meal_data=meal_data,
        cuisine_data=cuisine_data,
        rating_data=rating_data
    )


# =========================================================
# SEARCH
# =========================================================
@app.route('/search')
def search():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    query = request.args.get('query', '').strip()
    user_id = session['user_id']
    
    connection = get_db_connection()
    
    if query:
        connection.execute(
            "INSERT INTO Search_History (UserID, SearchText) VALUES (?, ?)",
            (user_id, query)
        )
        connection.commit()
    
    recipes = connection.execute(
        """
        SELECT Recipes.*, Meal_Types.Name AS MealType, Cuisines.Name AS Cuisine 
        FROM Recipes
        LEFT JOIN Meal_Types ON Recipes.MealTypeID = Meal_Types.MealTypeID
        LEFT JOIN Cuisines ON Recipes.CuisineID = Cuisines.CuisineID
        WHERE LOWER(Recipes.Title) LIKE LOWER(?)
        """,
        (f'%{query}%',)
    ).fetchall()
    
    connection.close()
    
    return render_template('search.html', recipes=recipes, query=query)


# =========================================================
# ADMIN USERS & ROLES
# =========================================================
@app.route("/admin/users")
def admin_users():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "Admin":
        flash("Access denied. Admin only.")
        return redirect(url_for("dashboard"))

    connection = get_db_connection()
    users = connection.execute(
        "SELECT UserID, Name, Email, Role, CreatedAt FROM Users ORDER BY CreatedAt DESC"
    ).fetchall()
    connection.close()

    return render_template("admin_users.html", users=users)


@app.route("/admin/user/<int:user_id>/role", methods=["POST"])
def change_user_role(user_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "Admin":
        flash("Access denied.")
        return redirect(url_for("dashboard"))

    if user_id == session["user_id"]:
        flash("You cannot change your own role.")
        return redirect(url_for("admin_users"))

    role = request.form.get("role")
    if role not in ["User", "Admin"]:
        flash("Invalid role.")
        return redirect(url_for("admin_users"))

    connection = get_db_connection()
    connection.execute("UPDATE Users SET Role = ? WHERE UserID = ?", (role, user_id))
    connection.commit()
    connection.close()

    flash("User role updated successfully.")
    return redirect(url_for("admin_users"))


@app.route("/admin/user/<int:user_id>/delete", methods=["POST"])
def delete_user(user_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "Admin":
        flash("Access denied.")
        return redirect(url_for("dashboard"))

    if user_id == session["user_id"]:
        flash("You cannot delete your own account.")
        return redirect(url_for("admin_users"))

    connection = get_db_connection()

    try:
        connection.execute("DELETE FROM Comments WHERE UserID = ?", (user_id,))
        connection.execute("DELETE FROM Ratings WHERE UserID = ?", (user_id,))
        connection.execute("DELETE FROM Favorites WHERE UserID = ?", (user_id,))
        connection.execute("DELETE FROM Search_History WHERE UserID = ?", (user_id,))
        connection.execute("DELETE FROM User_Preferences WHERE UserID = ?", (user_id,))

        shopping_lists = connection.execute(
            "SELECT ShoppingListID FROM Shopping_Lists WHERE UserID = ?", (user_id,)
        ).fetchall()

        for shopping_list in shopping_lists:
            connection.execute(
                "DELETE FROM Shopping_List_Items WHERE ShoppingListID = ?",
                (shopping_list["ShoppingListID"],)
            )

        connection.execute("DELETE FROM Shopping_Lists WHERE UserID = ?", (user_id,))

        recipes = connection.execute(
            "SELECT RecipeID FROM Recipes WHERE UserID = ?", (user_id,)
        ).fetchall()

        for recipe in recipes:
            recipe_id = recipe["RecipeID"]
            connection.execute("DELETE FROM Favorites WHERE RecipeID = ?", (recipe_id,))
            connection.execute("DELETE FROM Ratings WHERE RecipeID = ?", (recipe_id,))
            connection.execute("DELETE FROM Comments WHERE RecipeID = ?", (recipe_id,))
            connection.execute("DELETE FROM Recipe_Ingredients WHERE RecipeID = ?", (recipe_id,))
            connection.execute("DELETE FROM Nutrition WHERE RecipeID = ?", (recipe_id,))

        connection.execute("DELETE FROM Recipes WHERE UserID = ?", (user_id,))
        connection.execute("DELETE FROM Users WHERE UserID = ?", (user_id,))

        connection.commit()
        flash("User deleted successfully.")
    except Exception as error:
        connection.rollback()
        flash(f"Error deleting user: {error}")
    finally:
        connection.close()

    return redirect(url_for("admin_users"))


@app.route("/admin/recipes")
def admin_recipes():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "Admin":
        flash("Access denied. Admin only.")
        return redirect(url_for("dashboard"))

    connection = get_db_connection()
    recipes = connection.execute(
        """
        SELECT Recipes.RecipeID, Recipes.Title, Recipes.CookingTime, Recipes.Difficulty, Recipes.SpiceLevel, Recipes.DietType,
               Meal_Types.Name AS MealType, Cuisines.Name AS Cuisine, Users.Name AS Creator
        FROM Recipes
        JOIN Meal_Types ON Recipes.MealTypeID = Meal_Types.MealTypeID
        JOIN Cuisines ON Recipes.CuisineID = Cuisines.CuisineID
        JOIN Users ON Recipes.UserID = Users.UserID
        ORDER BY Recipes.CreatedAt DESC
        """
    ).fetchall()
    connection.close()

    return render_template("admin_recipes.html", recipes=recipes)


@app.route("/admin/recipe/<int:recipe_id>/delete", methods=["POST"])
def admin_delete_recipe(recipe_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "Admin":
        flash("Access denied. Admin only.")
        return redirect(url_for("dashboard"))

    connection = get_db_connection()

    try:
        connection.execute("DELETE FROM Favorites WHERE RecipeID = ?", (recipe_id,))
        connection.execute("DELETE FROM Ratings WHERE RecipeID = ?", (recipe_id,))
        connection.execute("DELETE FROM Comments WHERE RecipeID = ?", (recipe_id,))
        connection.execute("DELETE FROM Recipe_Ingredients WHERE RecipeID = ?", (recipe_id,))
        connection.execute("DELETE FROM Nutrition WHERE RecipeID = ?", (recipe_id,))
        connection.execute("DELETE FROM Recipes WHERE RecipeID = ?", (recipe_id,))

        connection.commit()
        flash("Recipe deleted successfully.")
    except Exception as error:
        connection.rollback()
        flash(f"Error deleting recipe: {error}")
    finally:
        connection.close()

    return redirect(url_for("admin_rules" if False else "admin_recipes"))


@app.route("/admin/ingredients", methods=["GET", "POST"])
def admin_ingredients():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "Admin":
        flash("Access denied. Admin only.")
        return redirect(url_for("dashboard"))

    connection = get_db_connection()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()

        if not name:
            flash("Ingredient name is required.")
        else:
            try:
                connection.execute(
                    "INSERT INTO Ingredients (Name, Category) VALUES (?, ?)",
                    (name, category)
                )
                connection.commit()
                flash("Ingredient added successfully.")
            except Exception:
                connection.rollback()
                flash("Ingredient already exists.")

    ingredients = connection.execute("SELECT * FROM Ingredients ORDER BY Name").fetchall()
    connection.close()

    return render_template("admin_ingredients.html", ingredients=ingredients)


@app.route("/admin/ingredient/<int:ingredient_id>/delete", methods=["POST"])
def admin_delete_ingredient(ingredient_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "Admin":
        flash("Access denied. Admin only.")
        return redirect(url_for("dashboard"))

    connection = get_db_connection()

    try:
        recipe_usage = connection.execute(
            "SELECT COUNT(*) AS Total FROM Recipe_Ingredients WHERE IngredientID = ?",
            (ingredient_id,)
        ).fetchone()

        if recipe_usage["Total"] > 0:
            flash("Cannot delete this ingredient because it is used in recipes.")
            connection.close()
            return redirect(url_for("admin_ingredients"))

        shopping_usage = connection.execute(
            "SELECT COUNT(*) AS Total FROM Shopping_List_Items WHERE IngredientID = ?",
            (ingredient_id,)
        ).fetchone()

        if shopping_usage["Total"]

        if shopping_usage["Total"] > 0:
            flash("Cannot delete this ingredient because it is used in shopping lists.")
            connection.close()
            return redirect(url_for("admin_ingredients"))

        connection.execute("DELETE FROM Ingredients WHERE IngredientID = ?", (ingredient_id,))
        connection.commit()
        flash("Ingredient deleted successfully.")
    except Exception as error:
        connection.rollback()
        flash(f"Error deleting ingredient: {error}")
    finally:
        connection.close()

    return redirect(url_for("admin_ingredients"))


if __name__ == "__main__":
    app.run(debug=True)