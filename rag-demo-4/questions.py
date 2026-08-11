"""The demo questions, with the chunk each one should retrieve.

Same five questions as rag-demo-2, so the two demos are directly comparable on
screen -- only the models behind them differ.

The shape changed slightly: each entry is a dict rather than a bare string,
carrying an `expect` marker. That marker is a substring that appears in exactly
one indexed chunk, which is what lets tune_alpha.py score retrieval
automatically instead of you eyeballing the ranked list. The correct answers
stay in comments; nothing is printed at runtime.

Ordered strongest-first: Q1-Q3 produce the most obviously fabricated answers
without RAG.
"""

QUESTIONS = [
    {
        # ROB007 = LiPo Battery Pack 48V, $199.99, Components, 150 in stock.
        # The SKU is a meaningless token to the model, so with no context it
        # invents a product outright -- usually a servo, sensor or controller
        # board, at an invented price.
        "q": "In the RoboShop catalogue, what product is SKU ROB007, "
             "what does it cost, and how many are in stock?",
        "expect": "ROB007",
    },
    {
        # ROB001 = Robo-Arm Deluxe, $1,299.99, 10kg payload, 1.2m reach, 6-axis.
        "q": "What is the price of the Robo-Arm Deluxe in the RoboShop catalogue, "
             "and what is its payload capacity and reach?",
        "expect": "ROB001",
    },
    {
        # ROB010 = Gripper Attachment Kit, 0.5-150mm grip, 50N max force, $249.99.
        "q": "What is the grip range and maximum force of the Gripper Attachment Kit "
             "sold by RoboShop, and what does it cost?",
        "expect": "ROB010",
    },
    {
        # Hyderabad, India (IN), region Telangana. With no shipping table the
        # model commonly invents "Andhra Pradesh", correct only before 2014.
        "q": "Does RoboShop ship to Hyderabad, and if so what region is it listed under?",
        "expect": "Hyderabad",
    },
    {
        # Tokyo, Japan (JP), region Kanto. Kept last on purpose: Tokyo/Kanto is
        # real-world public knowledge, so the model often gets the region right
        # by luck even with no access to the cities table. An honest
        # illustration that hallucination is not uniform -- it fails hardest on
        # private data.
        "q": "Does RoboShop ship to Tokyo, and what region is it listed under?",
        "expect": "Tokyo",
    },
]

# The same five targets asked WITHOUT the identifier -- no SKU, no exact product
# name, no city name. This cohort exists because of a real measurement problem.
#
# Every question in QUESTIONS above contains a rare literal token (ROB007,
# "Hyderabad"), which is exactly the case BM25 wins on its own. Scored against
# that set alone, every alpha from 0.2 to 1.0 gets 5/5 -- including pure BM25 --
# so the set cannot tell you anything about the right blend. It measures nothing.
#
# These are how a customer actually asks. They are the case where the embedder
# earns its keep, and scoring both cohorts is what makes the alpha curve
# discriminate. See tune_alpha.py.
PARAPHRASES = [
    {
        "q": "How much does the 48 volt battery pack cost, and how many are left?",
        "expect": "ROB007",
    },
    {
        "q": "What weight can the six-axis industrial arm handle, and how far "
             "can it extend?",
        "expect": "ROB001",
    },
    {
        "q": "How much clamping force does the adaptive three-finger tool provide?",
        "expect": "ROB010",
    },
    {
        "q": "Do you deliver anywhere in Telangana?",
        "expect": "Hyderabad",
    },
    {
        "q": "Do you deliver to the Kanto area of Japan?",
        "expect": "Tokyo",
    },
]

# Questions for ask_live.py, which holds no index and queries the databases
# directly. Nothing here is answerable from the embedded chunks -- that is the
# point of the split.
#
# Q1-Q3 hit MySQL and come back exact. Q4-Q6 hit MongoDB, which is EMPTY on a
# fresh environment, and the interesting behaviour is that the model reports
# zero honestly instead of inventing a sales figure.
LIVE_QUESTIONS = [
    # -> get_stock("ROB007"). Whatever the database says right now is correct;
    #    the RAG index would still be reporting its value from index time.
    "How many units of ROB007 are in stock right now?",

    # -> get_product(name="Gripper Attachment Kit") -> ROB010, $249.99.
    "What does the Gripper Attachment Kit cost, and is it in stock?",

    # -> get_product(sku="ROB012") -> Neural Network Accelerator, $1,499.99.
    "Tell me about SKU ROB012 -- what is it and what does it cost?",

    # -> get_sales_for_sku("ROB007"). Empty collection: expect "no sales
    #    recorded", not an invented number.
    "How many units of ROB007 have we sold, and what revenue did that generate?",

    # -> get_recent_orders(). Same.
    "What are our most recent orders?",

    # Two tools, two databases, one answer: MySQL stock plus MongoDB sales.
    "For the Robo-Arm Deluxe, how many are left in stock and how many have sold?",
]
