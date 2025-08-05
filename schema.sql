INSERT INTO core_product (ploidy, type, diameter, price)
VALUES ('diploid', 'steelhead', 4, 10.00)
RETURNING id;

INSERT INTO core_user (username, email, password, role, company, reliability_score)
VALUES ('johndoe', 'john@example.com', 'pbkdf2_sha256$390000$...', 'customer', 'John’s Fish Co.', 0.8)
RETURNING id;

INSERT INTO core_availability (product_id, year, week_number, available_quantity)
VALUES (1, 2025, 1, 100000);

INSERT INTO core_order (customer_id, availability_id, quantity, status, downpayment_amount, transport_cost, commission_rate)
VALUES (1, 1, 50000, 'pending', 750.00, 100.00, 5.00);

INSERT INTO core_customerevent (user_id, event_type, order_id, metadata)
VALUES (1, 'ORDER_CREATED', 1, '{"quantity": 50000}');