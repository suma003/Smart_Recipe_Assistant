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
        SELECT RecipeID, Title, CookingTime, Difficulty
        FROM Recipes WHERE UserID = ?
        ORDER BY CreatedAt DESC LIMIT 5
        """,
        (user_id,)
    ).fetchall()

    favorite_recipes = connection.execute(
        """
        SELECT Recipes.RecipeID, Recipes.Title, Recipes.CookingTime, Recipes.Difficulty
        FROM Favorites JOIN Recipes ON Favorites.RecipeID = Recipes.RecipeID
        WHERE Favorites.UserID = ?
        ORDER BY Favorites.CreatedAt DESC LIMIT 5
        """,
        (user_id,)
    ).fetchall()

    recent_searches = connection.execute(
        """
        SELECT SearchText, SearchDate FROM Search_History
        WHERE UserID = ? ORDER BY SearchDate DESC LIMIT 5
        """,
        (user_id,)
    ).fetchall()

    total_recipes = connection.execute("SELECT COUNT(*) AS count FROM Recipes WHERE UserID = ?", (user_id,)).fetchone()["count"]
    total_favorites = connection.execute("SELECT COUNT(*) AS count FROM Favorites WHERE UserID = ?", (user_id,)).fetchone()["count"]
    total_ratings = connection.execute("SELECT COUNT(*) AS count FROM Ratings WHERE UserID = ?", (user_id,)).fetchone()["count"]
    total_comments = connection.execute("SELECT COUNT(*) AS count FROM Comments WHERE UserID = ?", (user_id,)).fetchone()["count"]
    total_shopping_lists = connection.execute("SELECT COUNT(*) AS count FROM Shopping_Lists WHERE UserID = ?", (user_id,)).fetchone()["count"]

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
            Recipes.RecipeID, Recipes.Title, Recipes.Description,
            Recipes.CookingTime, Recipes.Difficulty, Recipes.ImageURL,
            Meal_Types.Name AS MealType, Cuisines.Name AS Cuisine, Users.Name AS Creator
        FROM Recipes
        JOIN Meal_Types ON Recipes.MealTypeID = Meal_Types.MealTypeID
        JOIN Cuisines ON Recipes.CuisineID = Cuisines.CuisineID
        JOIN Users ON Recipes.UserID = Users.UserID
        LEFT JOIN Recipe_Ingredients ON Recipes.RecipeID = Recipe_Ingredients.RecipeID
    """

    conditions = []
    parameters = []

    if search:
        conditions.append("Recipes.Title LIKE ?")
        parameters.append(f"%{search}%")
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

    query += "\n ORDER BY Recipes.CreatedAt DESC"

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
            Recipes.RecipeID, Recipes.Title, Recipes.Description,
            Recipes.CookingTime, Recipes.Difficulty, Recipes.ImageURL,
            Meal_Types.Name AS MealType, Cuisines.Name AS Cuisine, Users.Name AS Creator
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

        calories = request.form.get("calories", "").strip()
        protein = request.form.get("protein", "").strip()
        carbohydrates = request.form.get("carbohydrates", "").strip()
        fat = request.form.get("fat", "").strip()
        fiber = request.form.get("fiber", "").strip()

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
            (session["user_id"], meal_type_id, cuisine_id, title, description, cooking_time_value, difficulty, spice_level, diet_type, instructions, image_url),
        )
        recipe_id = cursor.lastrowid

        connection.execute(
            """
            INSERT INTO Nutrition (RecipeID, Calories, Protein, Carbohydrates, Fat, Fiber)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                recipe_id,
                float(calories) if calories else 0,
                float(protein) if protein else 0,
                float(carbohydrates) if carbohydrates else 0,
                float(fat) if fat else 0,
                float(fiber) if fiber else 0,
            ),
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

    if recipe is None:
        connection.close()
        return "Recipe not found", 404

    nutrition = connection.execute("SELECT * FROM Nutrition WHERE RecipeID = ?", (recipe_id,)).fetchone()

    ingredients = connection.execute(
        """
        SELECT Ingredients.Name, Recipe_Ingredients.Quantity, Recipe_Ingredients.Unit
        FROM Recipe_Ingredients
        JOIN Ingredients ON Recipe_Ingredients.IngredientID = Ingredients.IngredientID
        WHERE Recipe_Ingredients.RecipeID = ?
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
        FROM Ratings JOIN Users ON Ratings.UserID = Users.UserID
        WHERE Ratings.RecipeID = ? ORDER BY Ratings.CreatedAt DESC
        """,
        (recipe_id,)
    ).fetchall()

    avg_row = connection.execute(
        "SELECT AVG(Rating) AS AverageRating FROM Ratings WHERE RecipeID = ?",
        (recipe_id,)
    ).fetchone()

    comments = connection.execute(
        """
        SELECT Comments.CommentText, Comments.CreatedAt, Users.Name
        FROM Comments JOIN Users ON Comments.UserID = Users.UserID
        WHERE Comments.RecipeID = ? ORDER BY Comments.CreatedAt DESC
        """,
        (recipe_id,)
    ).fetchall()

    connection.close()

    avg_val = avg_row["AverageRating"] if avg_row and avg_row["AverageRating"] is not None else None

    return render_template(
        "recipe_detail.html",
        recipe=recipe,
        ingredients=ingredients,
        is_favorite=(favorite is not None),
        ratings=ratings,
        average_rating=avg_val,
        comments=comments,
        nutrition=nutrition
    )


# =========================================================
# EDIT RECIPE
# =========================================================
@app.route("/edit-recipe/<int:recipe_id>", methods=["GET", "POST"])
def edit_recipe(recipe_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    recipe = connection.execute("SELECT * FROM Recipes WHERE RecipeID = ?", (recipe_id,)).fetchone()

    if recipe is None:
        connection.close()
        flash("Recipe not found.")
        return redirect(url_for("recipes"))

    if recipe["UserID"] != session["user_id"]:
        connection.close()
        flash("You can only edit your own recipes.")
        return redirect(url_for("recipes"))

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

        calories = request.form.get("calories") or 0
        protein = request.form.get("protein") or 0
        carbohydrates = request.form.get("carbohydrates") or 0
        fat = request.form.get("fat") or 0
        fiber = request.form.get("fiber") or 0

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
                return redirect(url_for("edit_recipe", recipe_id=recipe_id))
        elif not image_url:
            image_url = recipe["ImageURL"]

        try:
            cooking_time_value = int(cooking_time)
            if cooking_time_value <= 0:
                raise ValueError
        except (TypeError, ValueError):
            connection.close()
            flash("Cooking time must be a positive number.")
            return redirect(url_for("edit_recipe", recipe_id=recipe_id))

        if not title or not instructions or not meal_type_id or not cuisine_id:
            connection.close()
            flash("Please fill all required fields.")
            return redirect(url_for("edit_recipe", recipe_id=recipe_id))

        connection.execute(
            """
            UPDATE Recipes
            SET Title = ?, Description = ?, MealTypeID = ?, CuisineID = ?,
                CookingTime = ?, Difficulty = ?, SpiceLevel = ?, DietType = ?,
                Instructions = ?, ImageURL = ?
            WHERE RecipeID = ?
            """,
            (title, description, meal_type_id, cuisine_id, cooking_time_value, difficulty, spice_level, diet_type, instructions, image_url, recipe_id)
        )

        existing_nutrition = connection.execute("SELECT NutritionID FROM Nutrition WHERE RecipeID = ?", (recipe_id,)).fetchone()
        if existing_nutrition:
            connection.execute(
                "UPDATE Nutrition SET Calories = ?, Protein = ?, Carbohydrates = ?, Fat = ?, Fiber = ? WHERE RecipeID = ?",
                (calories, protein, carbohydrates, fat, fiber, recipe_id)
            )
        else:
            connection.execute(
                "INSERT INTO Nutrition (RecipeID, Calories, Protein, Carbohydrates, Fat, Fiber) VALUES (?, ?, ?, ?, ?, ?)",
                (recipe_id, calories, protein, carbohydrates, fat, fiber)
            )

        connection.execute("DELETE FROM Recipe_Ingredients WHERE RecipeID = ?", (recipe_id,))
        all_ingredients_list = connection.execute("SELECT IngredientID FROM Ingredients").fetchall()
        selected_checkboxes = request.form.getlist("ingredients")

        for ing in all_ingredients_list:
            ing_id_str = str(ing["IngredientID"])
            quantity = request.form.get(f"quantity_{ing_id_str}", "").strip()
            unit = request.form.get(f"unit_{ing_id_str}", "").strip()
            is_checked = ing_id_str in selected_checkboxes

            if is_checked or quantity or unit:
                connection.execute(
                    "INSERT INTO Recipe_Ingredients (RecipeID, IngredientID, Quantity, Unit) VALUES (?, ?, ?, ?)",
                    (recipe_id, ing["IngredientID"], quantity if quantity else "As needed", unit if unit else "")
                )

        connection.commit()
        connection.close()

        flash("Recipe updated successfully!")
        return redirect(url_for("recipe_detail", recipe_id=recipe_id))

    meal_types = connection.execute("SELECT * FROM Meal_Types ORDER BY Name").fetchall()
    cuisines = connection.execute("SELECT * FROM Cuisines ORDER BY Name").fetchall()
    ingredients = connection.execute("SELECT * FROM Ingredients ORDER BY Name").fetchall()
    
    current_ing_rows = connection.execute(
        "SELECT IngredientID, Quantity, Unit FROM Recipe_Ingredients WHERE RecipeID = ?", (recipe_id,)
    ).fetchall()
    
    existing_ingredients_dict = {
        int(row["IngredientID"]): {"quantity": row["Quantity"], "unit": row["Unit"]}
        for row in current_ing_rows
    }
    
    nutrition = connection.execute("SELECT * FROM Nutrition WHERE RecipeID = ?", (recipe_id,)).fetchone()
    connection.close()

    return render_template(
        "edit_recipe.html",
        recipe=recipe,
        meal_types=meal_types,
        cuisines=cuisines,
        ingredients=ingredients,
        existing_ingredients_dict=existing_ingredients_dict,
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
    recipe_exists = connection.execute("SELECT RecipeID FROM Recipes WHERE RecipeID = ?", (recipe_id,)).fetchone()

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
    recipe_exists = connection.execute("SELECT RecipeID FROM Recipes WHERE RecipeID = ?", (recipe_id,)).fetchone()

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
            "UPDATE Ratings SET Rating = ?, Review = ?, CreatedAt = CURRENT_TIMESTAMP WHERE RatingID = ?",
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
    recipe_exists = connection.execute("SELECT RecipeID FROM Recipes WHERE RecipeID = ?", (recipe_id,)).fetchone()

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
        SELECT Recipes.RecipeID, Recipes.Title, Recipes.Description, Recipes.CookingTime,
               Recipes.Difficulty, Recipes.ImageURL, Meal_Types.Name AS MealType,
               Cuisines.Name AS Cuisine, Users.Name AS Creator
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
# USER PREFERENCES
# =========================================================
@app.route("/preferences", methods=["GET", "POST"])
def preferences():
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    user_id = session["user_id"]

    if request.method == "POST":
        spice_level = request.form.get("spice_level")
        diet_type = request.form.get("diet_type")
        max_cooking_time = request.form.get("max_cooking_time")
        difficulty = request.form.get("difficulty")
        calorie_preference = request.form.get("calorie_preference")

        existing = connection.execute("SELECT PreferenceID FROM User_Preferences WHERE UserID = ?", (user_id,)).fetchone()

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

    user_preferences = connection.execute("SELECT * FROM User_Preferences WHERE UserID = ?", (user_id,)).fetchone()
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

    preferences = connection.execute("SELECT * FROM User_Preferences WHERE UserID = ?", (user_id,)).fetchone()

    if not preferences:
        connection.close()
        flash("Please set your preferences first.")
        return redirect(url_for("preferences"))

    available_ids = session.get("available_ingredients", [])
    available_ids = set(int(x) for x in available_ids)

    recipes = connection.execute(
        """
        SELECT Recipes.*, Meal_Types.Name AS MealType, Cuisines.Name AS Cuisine
        FROM Recipes
        JOIN Meal_Types ON Recipes.MealTypeID = Meal_Types.MealTypeID
        JOIN Cuisines ON Recipes.CuisineID = Cuisines.CuisineID
        ORDER BY Recipes.CreatedAt DESC
        """
    ).fetchall()

    recommended_recipes = []

    for recipe in recipes:
        score = 0
        recipe_ingredients = connection.execute(
            "SELECT IngredientID FROM Recipe_Ingredients WHERE RecipeID = ?",
            (recipe["RecipeID"],)
        ).fetchall()

        recipe_ingredient_ids = {row["IngredientID"] for row in recipe_ingredients}

        if recipe_ingredient_ids:
            matched_ingredients = recipe_ingredient_ids & available_ids
            ingredient_percentage = len(matched_ingredients) / len(recipe_ingredient_ids)
            ingredient_score = ingredient_percentage * 40
            score += ingredient_score
        else:
            ingredient_percentage = 0

        preferred_meal = request.args.get("meal_type", "").strip()
        if preferred_meal and recipe["MealType"] == preferred_meal:
            score += 10

        preferred_cuisine = request.args.get("cuisine", "").strip()
        if preferred_cuisine and recipe["Cuisine"] == preferred_cuisine:
            score += 10

        max_time = preferences["MaxCookingTime"]
        if max_time:
            try:
                max_time = int(max_time)
                if recipe["CookingTime"] <= max_time:
                    score += 10
            except (TypeError, ValueError):
                pass

        if recipe["Difficulty"] == preferences["DifficultyPreference"]:
            score += 10

        if recipe["SpiceLevel"] == preferences["SpiceLevel"]:
            score += 10

        if recipe["DietType"] == preferences["DietType"]:
            score += 5

        rating = connection.execute(
            "SELECT AVG(Rating) AS AverageRating FROM Ratings WHERE RecipeID = ?",
            (recipe["RecipeID"],)
        ).fetchone()

        average_rating = rating["AverageRating"] if rating["AverageRating"] else 0
        rating_score = (average_rating / 5) * 5
        score += rating_score

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
        preferences=preferences
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
        SELECT Recipes.RecipeID, Recipes.Title, Recipes.Description, Recipes.CookingTime,
               Recipes.Difficulty, Recipes.ImageURL, Meal_Types.Name AS MealType,
               Cuisines.Name AS Cuisine, COUNT(DISTINCT Recipe_Ingredients.IngredientID) AS MatchedCount,
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

    recipe = connection.execute("SELECT RecipeID, Title FROM Recipes WHERE RecipeID = ?", (recipe_id,)).fetchone()
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
            "INSERT INTO Shopping_List_Items (ShoppingListID, IngredientID, Quantity, Unit) VALUES (?, ?, ?, ?)",
            (shopping_list_id, ingredient["IngredientID"], ingredient["Quantity"], ingredient["Unit"])
        )
        added_count += 1

    if added_count == 0:
        connection.execute("DELETE FROM Shopping_Lists WHERE ShoppingListID = ?", (shopping_list_id,))
        connection.commit()
        connection.close()
        flash("You already have all ingredients for this recipe.")
        return redirect(url_for("ingredient_recommendations"))

    connection.commit()
    connection.close()

    flash("Shopping list created successfully!")
    return redirect(url_for("shopping_list"))


# =========================================================
# SHOPPING LIST HELPER
# =========================================================
def get_or_create_default_shopping_list(connection, user_id):
    existing_list = connection.execute(
        "SELECT ShoppingListID FROM Shopping_Lists WHERE UserID = ? AND ListName = ?",
        (user_id, "My Shopping List")
    ).fetchone()

    if existing_list:
        return existing_list["ShoppingListID"]

    cursor = connection.execute(
        "INSERT INTO Shopping_Lists (UserID, ListName) VALUES (?, ?)",
        (user_id, "My Shopping List")
    )
    return cursor.lastrowid


# =========================================================
# ADD MISSING INGREDIENTS TO SHOPPING LIST
# =========================================================
@app.route("/add-missing-to-shopping-list/<int:recipe_id>", methods=["POST"])
def add_missing_to_shopping_list(recipe_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    raw_available = session.get("available_ingredients", [])
    try:
        available_ingredients = [int(x) for x in raw_available]
    except (TypeError, ValueError):
        available_ingredients = []

    connection = get_db_connection()
    shopping_list_id = get_or_create_default_shopping_list(connection, user_id)

    recipe_ingredients = connection.execute(
        "SELECT IngredientID, Quantity, Unit FROM Recipe_Ingredients WHERE RecipeID = ?",
        (recipe_id,)
    ).fetchall()

    added_count = 0
    for item in recipe_ingredients:
        ing_id = item["IngredientID"]

        if ing_id in available_ingredients:
            continue

        existing_item = connection.execute(
            "SELECT ItemID, Quantity FROM Shopping_List_Items WHERE ShoppingListID = ? AND IngredientID = ? AND IsPurchased = 0",
            (shopping_list_id, ing_id)
        ).fetchone()

        if existing_item:
            new_quantity = (existing_item["Quantity"] or 0) + (item["Quantity"] or 0)
            connection.execute(
                "UPDATE Shopping_List_Items SET Quantity = ? WHERE ItemID = ?",
                (new_quantity, existing_item["ItemID"])
            )
        else:
            connection.execute(
                "INSERT INTO Shopping_List_Items (ShoppingListID, IngredientID, Quantity, Unit, IsPurchased) VALUES (?, ?, ?, ?, 0)",
                (shopping_list_id, ing_id, item["Quantity"], item["Unit"])
            )

        added_count += 1

    connection.commit()
    connection.close()

    if added_count == 0:
        flash("You already have all ingredients for this recipe.")
    else:
        flash("Missing ingredients added to your shopping list successfully!")

    return redirect(url_for("shopping_list"))


# =========================================================
# SHOPPING LIST ROUTE (VIEW)
# =========================================================
@app.route("/shopping-list")
def shopping_list():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    connection = get_db_connection()

    shopping_items = connection.execute(
        """
        SELECT Shopping_List_Items.ItemID, Ingredients.Name, Shopping_List_Items.Quantity,
               Shopping_List_Items.Unit, Shopping_List_Items.IsPurchased
        FROM Shopping_List_Items
        JOIN Shopping_Lists ON Shopping_List_Items.ShoppingListID = Shopping_Lists.ShoppingListID
        JOIN Ingredients ON Shopping_List_Items.IngredientID = Ingredients.IngredientID
        WHERE Shopping_Lists.UserID = ?
        ORDER BY Shopping_List_Items.IsPurchased ASC, Ingredients.Name ASC
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

    connection.execute(
        "DELETE FROM Shopping_List_Items WHERE ShoppingListID IN (SELECT ShoppingListID FROM Shopping_Lists WHERE UserID = ?)",
        (user_id,)
    )
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

    user_id = session["user_id"]
    connection = get_db_connection()

    item = connection.execute(
        """
        SELECT Shopping_List_Items.ItemID, Shopping_List_Items.IsPurchased
        FROM Shopping_List_Items
        JOIN Shopping_Lists ON Shopping_List_Items.ShoppingListID = Shopping_Lists.ShoppingListID
        WHERE Shopping_List_Items.ItemID = ? AND Shopping_Lists.UserID = ?
        """,
        (item_id, user_id)
    ).fetchone()

    if item:
        new_status = 0 if item["IsPurchased"] == 1 else 1
        connection.execute(
            "UPDATE Shopping_List_Items SET IsPurchased = ? WHERE ItemID = ?",
            (new_status, item_id)
        )
        connection.commit()
    else:
        flash("Item not found or you do not have permission to change it.")

    connection.close()
    return redirect(url_for("shopping_list"))


# =========================================================
# DELETE SHOPPING ITEM ROUTE
# =========================================================
@app.route("/delete-shopping-item/<int:item_id>", methods=["POST"])
def delete_shopping_item(item_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    connection = get_db_connection()

    item = connection.execute(
        """
        SELECT Shopping_List_Items.ItemID
        FROM Shopping_List_Items
        JOIN Shopping_Lists ON Shopping_List_Items.ShoppingListID = Shopping_Lists.ShoppingListID
        WHERE Shopping_List_Items.ItemID = ? AND Shopping_Lists.UserID = ?
        """,
        (item_id, user_id)
    ).fetchone()

    if item:
        connection.execute("DELETE FROM Shopping_List_Items WHERE ItemID = ?", (item_id,))
        connection.commit()
        flash("Item deleted successfully!")
    else:
        flash("Item not found or you do not have permission to delete it.")

    connection.close()
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
        meal_data=meal_data,
        cuisine_data=cuisine_data,
        rating_data=rating_data
    )


# =========================================================
# SEARCH REDIRECT
# =========================================================
@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query', '').strip()
    return redirect(url_for('recipes', search=query))


if __name__ == "__main__":
    app.run(debug=True)