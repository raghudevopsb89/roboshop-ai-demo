"""The demo questions, plus the ground truth held in the RoboShop SQL data.

Every one of these is answerable ONLY from the catalogue and cities tables.
The 12 products are invented for RoboShop -- no base model has ever seen them --
so without RAG the model must either refuse or fabricate.

One honest caveat, unlike rag-demo-1: "RoboShop" is a real, widely-used public
DevOps training application, so the model DOES have some genuine knowledge of the
microservice architecture. Questions about *the product catalogue* fail cleanly
without RAG; questions like "what services does RoboShop have" would half-succeed
and make a muddier demo. That is why every question below is about catalogue or
shipping data rather than architecture.

Ordered strongest-first: Q1-Q3 produce the most obviously fabricated answers.
"""

QUESTIONS = [
    {
        # No-RAG failure: the SKU is a meaningless token to the model, so it
        # invents a product outright -- usually a servo, sensor or controller,
        # at an invented price.
        "q": "In the RoboShop catalogue, what product is SKU ROB007, "
             "what does it cost, and how many are in stock?",
        "truth": "LiPo Battery Pack 48V -- $199.99, Components category, "
                 "150 in stock. 48V 20Ah (960Wh), built-in BMS.",
    },
    {
        # No-RAG failure: invents a payload figure and a price, typically an
        # order of magnitude off, and often attributes it to a real vendor
        # such as Universal Robots or FANUC.
        "q": "What is the price of the Robo-Arm Deluxe in the RoboShop "
             "catalogue, and what is its payload capacity and reach?",
        "truth": "$1,299.99 -- 10kg payload, 1.2m reach, 6-axis movement. "
                 "SKU ROB001, Robots category, 25 in stock.",
    },
    {
        # No-RAG failure: invents grip range and force numbers, and frequently
        # invents a SKU in a completely different format.
        "q": "What is the grip range and maximum force of the Gripper "
             "Attachment Kit sold by RoboShop, and what does it cost?",
        "truth": "0.5-150mm grip range, 50N max force, $249.99. SKU ROB010, "
                 "Accessories category, 85 in stock.",
    },
    {
        # No-RAG failure: the model has no shipping table, so it either refuses
        # or asserts coverage confidently and invents the wrong region
        # (commonly "Andhra Pradesh", which was correct only before 2014).
        "q": "Does RoboShop ship to Hyderabad, and if so what region is it "
             "listed under?",
        "truth": "Yes -- Hyderabad, India (IN), region Telangana.",
    },
    {
        # Weakest demo question, kept last on purpose: Tokyo/Kanto is real-world
        # public knowledge, so the model often gets the region right by luck
        # even with no access to the cities table. An honest illustration that
        # hallucination is not uniform -- it fails hardest on private data.
        "q": "Does RoboShop ship to Tokyo, and what region is it listed under?",
        "truth": "Yes -- Tokyo, Japan (JP), region Kanto.",
    },
]
