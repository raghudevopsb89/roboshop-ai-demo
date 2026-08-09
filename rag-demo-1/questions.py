"""The demo questions, plus the ground truth held in the SQL database.

Every one of these is answerable ONLY from company.db. A base model has never
seen this data, so without RAG it must either refuse or invent an answer.

Ordered strongest-first for demo purposes: Q1, Q2 and Q3 produce the most
obviously fabricated answers without RAG.
"""

QUESTIONS = [
    {
        # No-RAG failure: invents "$12.8 million" and a "Home & Kitchen segment"
        # -- Nimbus sells software, it has no homeware categories at all.
        "q": "What was Nimbus Retail Analytics' total revenue in the APAC region "
             "for FY2024-Q3, and which product line contributed the most?",
        "truth": "$6,663,700 total. FlowCast contributed the most at $2,967,500.",
    },
    {
        # No-RAG failure: invents a lead named "Rohan Patil", fake engineer IDs,
        # and a budget denominated in Indian rupee lakhs.
        "q": "Who leads the Atlas Migration project at Nimbus Retail Analytics, "
             "how many engineers are on it, and what is its budget?",
        "truth": "Sofia Marchetti leads PRJ-207, 9 engineers, $1,250,000 budget.",
    },
    {
        # No-RAG failure: invents employee ID "EID-1234" and the wrong manager.
        "q": "What is the employee ID of Aisha Rahman at Nimbus Retail Analytics, "
             "and who is her manager?",
        "truth": "NRA-1119, Senior ML Engineer, manager is Marcus Ohene.",
    },
    {
        # No-RAG failure: invents a "Director of Operations" approver role that
        # does not exist anywhere in the company.
        "q": "At Nimbus Retail Analytics, who must approve a purchase of 150,000 USD?",
        "truth": "Both Head of Finance (Tomas Lindqvist) and VP of Engineering "
                 "(Priya Venkatesan), because it exceeds 100,000 USD.",
    },
    {
        # Weakest demo question: 30 minutes is a common industry SLA figure, so
        # the model sometimes guesses it correctly by luck -- though it still
        # fabricates supporting detail (a fake incident ID, a resolution target).
        # Kept last as an honest illustration that hallucination is not uniform.
        "q": "At Nimbus Retail Analytics, what is the first-response SLA for a "
             "Severity-1 incident for Enterprise tier customers?",
        "truth": "30 minutes for Enterprise tier (Standard tier is 8 business hours).",
    },
]
