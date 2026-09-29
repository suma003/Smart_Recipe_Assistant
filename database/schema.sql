-- =========================================================
-- SMART RECIPE ASSISTANT
-- Complete SQLite Database Schema (Updated for Step 12)
-- =========================================================

PRAGMA foreign_keys = ON;


-- =========================================================
-- 1. USERS TABLE
-- =========================================================

CREATE TABLE IF NOT EXISTS Users (
    UserID INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL,
    Email TEXT NOT NULL UNIQUE,
    Password TEXT NOT NULL,
    Role TEXT NOT NULL DEFAULT 'User'
        CHECK (Role IN ('User', 'Admin')),
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- =========================================================
-- 2. USER PREFERENCES TABLE
-- =========================================================

CREATE TABLE IF NOT EXISTS User_Preferences (
    PreferenceID INTEGER PRIMARY KEY AUTOINCREMENT,
    UserID INTEGER NOT NULL UNIQUE,
    SpiceLevel TEXT
        CHECK (SpiceLevel IN ('Mild', 'Medium', 'Spicy')),
    DietType TEXT
        CHECK (
            DietType IN (
                'Regular',
                'Vegetarian',
                'Vegan',
                'Low Calorie',
                'High Protein',
                'Gluten Free'
            )
        ),
    MaxCookingTime INTEGER
        CHECK (MaxCookingTime > 0),
    DifficultyPreference TEXT
        CHECK (
            DifficultyPreference IN (
                'Easy',
                'Medium',
                'Hard'
            )
        ),
    CaloriePreference INTEGER
        CHECK (CaloriePreference > 0),
    FOREIGN KEY (UserID)
        REFERENCES Users(UserID)
        ON DELETE CASCADE
);


-- =========================================================
-- 3. MEAL TYPES TABLE
-- =========================================================

CREATE TABLE IF NOT EXISTS Meal_Types (
    MealTypeID INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL UNIQUE
);


-- =========================================================
-- 4. CUISINES TABLE
-- =========================================================

CREATE TABLE IF NOT EXISTS Cuisines (
    CuisineID INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL UNIQUE
);


-- =========================================================
-- 5. RECIPES TABLE (UPDATED WITH SpiceLevel & DietType)
-- =========================================================

CREATE TABLE IF NOT EXISTS Recipes (
    RecipeID INTEGER PRIMARY KEY AUTOINCREMENT,
    UserID INTEGER NOT NULL,
    MealTypeID INTEGER NOT NULL,
    CuisineID INTEGER NOT NULL,
    Title TEXT NOT NULL,
    Description TEXT,
    CookingTime INTEGER NOT NULL
        CHECK (CookingTime > 0),
    Difficulty TEXT NOT NULL
        CHECK (
            Difficulty IN (
                'Easy',
                'Medium',
                'Hard'
            )
        ),
    SpiceLevel TEXT DEFAULT 'Medium'
        CHECK (
            SpiceLevel IN (
                'Mild',
                'Medium',
                'Spicy'
            )
        ),
    DietType TEXT DEFAULT 'Regular'
        CHECK (
            DietType IN (
                'Regular',
                'Vegetarian',
                'Vegan',
                'Low Calorie',
                'High Protein',
                'Gluten Free'
            )
        ),
    Instructions TEXT NOT NULL,
    ImageURL TEXT,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (UserID)
        REFERENCES Users(UserID)
        ON DELETE CASCADE,
    FOREIGN KEY (MealTypeID)
        REFERENCES Meal_Types(MealTypeID)
        ON DELETE RESTRICT,
    FOREIGN KEY (CuisineID)
        REFERENCES Cuisines(CuisineID)
        ON DELETE RESTRICT
);


-- =========================================================
-- 6. INGREDIENTS TABLE
-- =========================================================

CREATE TABLE IF NOT EXISTS Ingredients (
    IngredientID INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL UNIQUE,
    Category TEXT
);


-- =========================================================
-- 7. RECIPE INGREDIENTS TABLE
-- =========================================================

CREATE TABLE IF NOT EXISTS Recipe_Ingredients (
    RecipeIngredientID INTEGER PRIMARY KEY AUTOINCREMENT,
    RecipeID INTEGER NOT NULL,
    IngredientID INTEGER NOT NULL,
    Quantity REAL
        CHECK (Quantity > 0),
    Unit TEXT,

    FOREIGN KEY (RecipeID)
        REFERENCES Recipes(RecipeID)
        ON DELETE CASCADE,
    FOREIGN KEY (IngredientID)
        REFERENCES Ingredients(IngredientID)
        ON DELETE RESTRICT,
    UNIQUE (RecipeID, IngredientID)
);


-- =========================================================
-- 8. FAVORITES TABLE
-- =========================================================

CREATE TABLE IF NOT EXISTS Favorites (
    FavoriteID INTEGER PRIMARY KEY AUTOINCREMENT,
    UserID INTEGER NOT NULL,
    RecipeID INTEGER NOT NULL,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (UserID)
        REFERENCES Users(UserID)
        ON DELETE CASCADE,
    FOREIGN KEY (RecipeID)
        REFERENCES Recipes(RecipeID)
        ON DELETE CASCADE,
    UNIQUE (UserID, RecipeID)
);


-- =========================================================
-- 9. RATINGS TABLE
-- =========================================================

CREATE TABLE IF NOT EXISTS Ratings (
    RatingID INTEGER PRIMARY KEY AUTOINCREMENT,
    UserID INTEGER NOT NULL,
    RecipeID INTEGER NOT NULL,
    Rating INTEGER NOT NULL
        CHECK (Rating BETWEEN 1 AND 5),
    Review TEXT,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (UserID)
        REFERENCES Users(UserID)
        ON DELETE CASCADE,
    FOREIGN KEY (RecipeID)
        REFERENCES Recipes(RecipeID)
        ON DELETE CASCADE,
    UNIQUE (UserID, RecipeID)
);


-- =========================================================
-- 10. COMMENTS TABLE
-- =========================================================

CREATE TABLE IF NOT EXISTS Comments (
    CommentID INTEGER PRIMARY KEY AUTOINCREMENT,
    UserID INTEGER NOT NULL,
    RecipeID INTEGER NOT NULL,
    CommentText TEXT NOT NULL,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (UserID)
        REFERENCES Users(UserID)
        ON DELETE CASCADE,
    FOREIGN KEY (RecipeID)
        REFERENCES Recipes(RecipeID)
        ON DELETE CASCADE
);


-- =========================================================
-- 11. SEARCH HISTORY TABLE
-- =========================================================

CREATE TABLE IF NOT EXISTS Search_History (
    SearchID INTEGER PRIMARY KEY AUTOINCREMENT,
    UserID INTEGER NOT NULL,
    SearchText TEXT NOT NULL,
    SearchDate TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (UserID)
        REFERENCES Users(UserID)
        ON DELETE CASCADE
);


-- =========================================================
-- 12. SHOPPING LISTS TABLE
-- =========================================================

CREATE TABLE IF NOT EXISTS Shopping_Lists (
    ShoppingListID INTEGER PRIMARY KEY AUTOINCREMENT,
    UserID INTEGER NOT NULL,
    ListName TEXT NOT NULL,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (UserID)
        REFERENCES Users(UserID)
        ON DELETE CASCADE
);


-- =========================================================
-- 13. SHOPPING LIST ITEMS TABLE
-- =========================================================

CREATE TABLE IF NOT EXISTS Shopping_List_Items (
    ItemID INTEGER PRIMARY KEY AUTOINCREMENT,
    ShoppingListID INTEGER NOT NULL,
    IngredientID INTEGER NOT NULL,
    Quantity REAL
        CHECK (Quantity > 0),
    Unit TEXT,
    IsPurchased INTEGER NOT NULL DEFAULT 0
        CHECK (IsPurchased IN (0, 1)),

    FOREIGN KEY (ShoppingListID)
        REFERENCES Shopping_Lists(ShoppingListID)
        ON DELETE CASCADE,
    FOREIGN KEY (IngredientID)
        REFERENCES Ingredients(IngredientID)
        ON DELETE RESTRICT
);


-- =========================================================
-- 14. NUTRITION TABLE
-- =========================================================

CREATE TABLE IF NOT EXISTS Nutrition (
    NutritionID INTEGER PRIMARY KEY AUTOINCREMENT,
    RecipeID INTEGER NOT NULL UNIQUE,
    Calories REAL
        CHECK (Calories >= 0),
    Protein REAL
        CHECK (Protein >= 0),
    Carbohydrates REAL
        CHECK (Carbohydrates >= 0),
    Fat REAL
        CHECK (Fat >= 0),
    Fiber REAL
        CHECK (Fiber >= 0),

    FOREIGN KEY (RecipeID)
        REFERENCES Recipes(RecipeID)
        ON DELETE CASCADE
);


-- =========================================================
-- INDEXES
-- =========================================================

CREATE INDEX IF NOT EXISTS idx_recipes_user
ON Recipes(UserID);

CREATE INDEX IF NOT EXISTS idx_recipes_mealtype
ON Recipes(MealTypeID);

CREATE INDEX IF NOT EXISTS idx_recipes_cuisine
ON Recipes(CuisineID);

CREATE INDEX IF NOT EXISTS idx_recipe_ingredients_recipe
ON Recipe_Ingredients(RecipeID);

CREATE INDEX IF NOT EXISTS idx_recipe_ingredients_ingredient
ON Recipe_Ingredients(IngredientID);

CREATE INDEX IF NOT EXISTS idx_favorites_user
ON Favorites(UserID);

CREATE INDEX IF NOT EXISTS idx_ratings_recipe
ON Ratings(RecipeID);

CREATE INDEX IF NOT EXISTS idx_comments_recipe
ON Comments(RecipeID);

CREATE INDEX IF NOT EXISTS idx_search_history_user
ON Search_History(UserID);

CREATE INDEX IF NOT EXISTS idx_shopping_lists_user
ON Shopping_Lists(UserID);


-- =========================================================
-- DEFAULT MEAL TYPES
-- =========================================================

INSERT OR IGNORE INTO Meal_Types (Name)
VALUES
    ('Breakfast'),
    ('Lunch'),
    ('Dinner'),
    ('Snack'),
    ('Dessert');


-- =========================================================
-- DEFAULT CUISINES
-- =========================================================

INSERT OR IGNORE INTO Cuisines (Name)
VALUES
    ('Bangladeshi'),
    ('Indian'),
    ('Italian'),
    ('Chinese'),
    ('Thai'),
    ('Japanese'),
    ('Mexican');


-- =========================================================
-- DEFAULT INGREDIENTS
-- =========================================================

INSERT OR IGNORE INTO Ingredients (Name, Category)
VALUES
    ('Chicken', 'Meat'),
    ('Potato', 'Vegetable'),
    ('Rice', 'Grain'),
    ('Onion', 'Vegetable'),
    ('Garlic', 'Vegetable'),
    ('Ginger', 'Vegetable'),
    ('Tomato', 'Vegetable'),
    ('Carrot', 'Vegetable'),
    ('Egg', 'Protein'),
    ('Milk', 'Dairy'),
    ('Cheese', 'Dairy'),
    ('Flour', 'Grain'),
    ('Salt', 'Spice'),
    ('Sugar', 'Sweetener'),
    ('Chili', 'Spice'),
    ('Turmeric', 'Spice'),
    ('Cumin', 'Spice'),
    ('Black Pepper', 'Spice'),
    ('Soy Sauce', 'Sauce'),
    ('Olive Oil', 'Oil');

-- =========================================================
-- END OF DATABASE SCHEMA
-- =========================================================