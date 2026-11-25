# Evaluation: qwen2.5-coder:7b, 25 questions (2026-11-25)

| Metric | Value |
|---|---|
| Execution accuracy (result matches the reference SQL) | 76% |
| Memos whose numbers are all in the query result | 79% |
| Valid SQL on the first try | 92% |
| Valid SQL after retries with the error message | 96% |
| Median seconds per question (CPU runner) | 54 |

| # | Question | Correct | Grounded | SQL tries | Seconds |
|---|---|---|---|---|---|
| [q01](memos/q01.md) | How many orders were delivered to customers? | yes | no | 1 | 80 |
| [q02](memos/q02.md) | What share of delivered orders arrived after the promised date? | yes | no | 1 | 56 |
| [q03](memos/q03.md) | What is the average review score for late deliveries compared with on-time deliveries? | no | yes | 1 | 53 |
| [q04](memos/q04.md) | Which 5 product categories sold the most in item revenue (price, without freight)? | yes | yes | 1 | 50 |
| [q05](memos/q05.md) | Which 5 customer states have the highest late delivery rate, among states with at least 1000 delivered orders? | no | no | 3 | 111 |
| [q06](memos/q06.md) | How did the number of orders per month change from January 2017 to August 2018? | yes | yes | 1 | 61 |
| [q07](memos/q07.md) | What share of orders is paid mainly with each payment type (credit_card, boleto, voucher, debit_card)? | no | yes | 1 | 56 |
| [q08](memos/q08.md) | What is the average number of days from purchase to delivery for delivered orders? | yes | yes | 1 | 32 |
| [q09](memos/q09.md) | Which 5 customer states wait the longest on average for delivery, in days from purchase? | no | yes | 1 | 63 |
| [q10](memos/q10.md) | What share of customers placed more than one order? | yes | no | 1 | 61 |
| [q11](memos/q11.md) | What is the average order value (items plus freight paid) for delivered orders? | yes | yes | 1 | 40 |
| [q12](memos/q12.md) | Which 5 sellers had the most item revenue, and from which state are they? | yes | no | 1 | 106 |
| [q13](memos/q13.md) | What share of orders was canceled? | yes | no | 1 | 76 |
| [q14](memos/q14.md) | How many distinct sellers are there in each of the 3 states with the most sellers? | yes | yes | 1 | 44 |
| [q15](memos/q15.md) | For which 5 categories with at least 500 items sold is freight the largest share of the item price? | no | yes | 1 | 56 |
| [q16](memos/q16.md) | What is the average review score of orders delivered more than 10 days after the promised date? | yes | yes | 1 | 41 |
| [q17](memos/q17.md) | How many installments do credit card orders use on average? | yes | yes | 1 | 40 |
| [q18](memos/q18.md) | What was the total payment value of all orders placed in 2017? | yes | yes | 1 | 44 |
| [q19](memos/q19.md) | What share of delivered orders got a 1-star review? | yes | yes | 1 | 39 |
| [q20](memos/q20.md) | How did the monthly late delivery rate evolve between January 2017 and August 2018? | yes | yes | 1 | 69 |
| [q21](memos/q21.md) | What share of item revenue comes from sellers in São Paulo state (SP)? | yes | yes | 1 | 47 |
| [q22](memos/q22.md) | Which 3 product categories have the lowest average review score, among categories with at least 1000 reviewed orders? Use the category of each order's first item and leave out the 'unknown' category. | no | yes | 2 | 72 |
| [q23](memos/q23.md) | What is the average number of items per order, for orders with at least one item? | yes | yes | 1 | 36 |
| [q24](memos/q24.md) | In which month between January 2017 and August 2018 were the most orders placed, and how many? | yes | yes | 1 | 41 |
| [q25](memos/q25.md) | What share of orders shipped to customers in the seller's own state? Count orders whose first item's seller is in the customer's state. | yes | yes | 1 | 54 |
