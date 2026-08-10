"""The demo questions for the live-data demo.

Q1-Q3 are catalogue questions: they hit MySQL and should come back exactly right.
Q4-Q6 are sale questions: they hit MongoDB, which on a fresh environment is
EMPTY -- and the point of those is that the model reports zero honestly instead
of inventing a sales figure. That is the behaviour demo 1 could not manage.

The correct answers are noted in comments for whoever maintains this file.
Nothing is printed at runtime -- you read the model's answer directly.
"""

QUESTIONS = [
    # -> get_stock("ROB007"). Live value; 150 on a freshly loaded catalogue,
    #    but whatever the database says right now is the right answer.
    "How many units of ROB007 are in stock right now?",

    # -> get_product(name="Gripper Attachment Kit") -> ROB010, $249.99, 85 stock.
    "What does the Gripper Attachment Kit cost, and is it in stock?",

    # -> get_product(sku="ROB012") -> Neural Network Accelerator, $1,499.99.
    "Tell me about SKU ROB012 -- what is it and what does it cost?",

    # -> get_sales_for_sku("ROB007"). Empty orders collection: the model should
    #    say no sales have been recorded, NOT invent units or revenue.
    "How many units of ROB007 have we sold, and what revenue did that generate?",

    # -> get_recent_orders(). Same: should report that there are no orders.
    "What are our most recent orders?",

    # Two tools in one question: catalogue stock (MySQL) plus sales (MongoDB).
    # A 3B model often manages only one of the two -- an honest look at the
    # limits of small-model tool calling.
    "For the Robo-Arm Deluxe, how many are left in stock and how many have sold?",
]
