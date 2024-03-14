import psycopg2

# Connect to the PostgreSQL database
conn = psycopg2.connect(database="task1_database", user="postgres", password="12345", host="localhost", port="5432")
cur = conn.cursor()

# Execute a SELECT query to retrieve all users
cur.execute("SELECT * FROM calorie_intake")
users = cur.fetchall()

# Print the users
for user in users:
    print(user)

# Close the cursor and connection
cur.close()
conn.close()
