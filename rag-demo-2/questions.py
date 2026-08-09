"""The demo questions.

Every one of these is answerable ONLY from the catalogue and cities tables.
The 12 products are invented for RoboShop -- no base model has ever seen them --
so without RAG the model must either refuse or fabricate.

One honest caveat: "RoboShop" is a real, widely-used public DevOps training
application, so the model DOES have some genuine knowledge of the microservice
architecture. Questions about *the product catalogue* fail cleanly without RAG;
questions like "what services does RoboShop have" would half-succeed and make a
muddier demo. That is why every question below is about catalogue or shipping
data rather than architecture.

The correct answers are noted in the comments for whoever maintains this file.
They are NOT printed -- on screen you compare the two model answers directly.

Ordered strongest-first: Q1-Q3 produce the most obviously fabricated answers.
"""

QUESTIONS = [
    # ROB007 = LiPo Battery Pack 48V, $199.99, Components, 150 in stock.
    # No-RAG failure: the SKU is a meaningless token to the model, so it invents
    # a product outright -- usually a servo, sensor or controller board, at an
    # invented price.
    "In the RoboShop catalogue, what product is SKU ROB007, "
    "what does it cost, and how many are in stock?",

    # ROB001 = Robo-Arm Deluxe, $1,299.99, 10kg payload, 1.2m reach, 6-axis.
    # No-RAG failure: invents a payload figure and a price, typically an order of
    # magnitude off, and often attributes it to a real vendor such as Universal
    # Robots or FANUC.
    "What is the price of the Robo-Arm Deluxe in the RoboShop catalogue, "
    "and what is its payload capacity and reach?",

    # ROB010 = Gripper Attachment Kit, 0.5-150mm grip, 50N max force, $249.99.
    # No-RAG failure: invents grip range and force numbers, and frequently
    # invents a SKU in a completely different format.
    "What is the grip range and maximum force of the Gripper Attachment Kit "
    "sold by RoboShop, and what does it cost?",

    # Hyderabad, India (IN), region Telangana.
    # No-RAG failure: the model has no shipping table, so it either refuses or
    # asserts coverage confidently and invents the wrong region (commonly
    # "Andhra Pradesh", which was correct only before 2014).
    "Does RoboShop ship to Hyderabad, and if so what region is it listed under?",

    # Tokyo, Japan (JP), region Kanto.
    # Weakest demo question, kept last on purpose: Tokyo/Kanto is real-world
    # public knowledge, so the model often gets the region right by luck even
    # with no access to the cities table. An honest illustration that
    # hallucination is not uniform -- it fails hardest on private data.
    "Does RoboShop ship to Tokyo, and what region is it listed under?",
]
